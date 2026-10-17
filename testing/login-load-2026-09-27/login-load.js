import http from 'k6/http';
import { check } from 'k6';
import crypto from 'k6/crypto';
import encoding from 'k6/encoding';
import exec from 'k6/execution';
import { SharedArray } from 'k6/data';
import { Rate, Trend } from 'k6/metrics';

// Login load test: each iteration performs a complete Keycloak PKCE login.
// Flow: authorization page -> credential submission -> code/token exchange.
// This measures the authentication path, not dashboard loading or attendance.
const issuer = 'https://auth.152-53-33-198.sslip.io/realms/uniattend';
const clientId = 'uniattend-mobile';
const redirectUri = 'uniattend://auth/callback';
// Separate runs used LOAD_USERS=20, 50, 100 and 200 for burst testing.
// LOAD_PATTERN=controlled instead treats LOAD_USERS as login starts per minute.
const loadUsers = Number(__ENV.LOAD_USERS || 200);
const loadPattern = __ENV.LOAD_PATTERN || 'stress';

// Load test accounts from an external CSV: header, then username,password rows.
// SharedArray avoids making a separate full copy of the account list for each VU.
const accounts = new SharedArray('login load accounts', () => {
  const lines = open(__ENV.USERS_FILE).replace(/^\uFEFF/, '').trim().split(/\r?\n/);
  return lines.slice(1).map((line) => {
    const fields = line.split(',').map((field) => field.replace(/^"|"$/g, ''));
    return { username: fields[0], password: fields[1] };
  });
});

// Require enough accounts for the requested test size before sending requests.
if (accounts.length < loadUsers) {
  throw new Error(`Need ${loadUsers} accounts but only ${accounts.length} were loaded`);
}

// Trend collects complete-login times in milliseconds; Rate collects failures.
const loginDuration = new Trend('login_load_duration', true);
const loginFailures = new Rate('login_load_failures');

const scenario = loadPattern === 'controlled'
  ? {
      // Spread login starts over one minute, independently of response speed.
      // Example: 200/min is about 3.33 starts/second, not 200 concurrent users.
      executor: 'constant-arrival-rate',
      rate: loadUsers,
      timeUnit: '1m',
      duration: '1m',
      // VUs are workers. k6 can allocate more if logins overlap, up to maxVUs.
      preAllocatedVUs: Math.min(50, loadUsers),
      maxVUs: loadUsers,
      gracefulStop: '30s',
    }
  : {
      // Burst: start the configured VUs together, with one login per VU.
      executor: 'per-vu-iterations',
      vus: loadUsers,
      iterations: 1,
      // This is a safety limit for the run, not the acceptable login duration.
      maxDuration: '5m',
      gracefulStop: '30s',
    };

export const options = {
  scenarios: { login_load: scenario },
  thresholds: {
    // Both must pass: p95 below 3 seconds and failed logins strictly below 1%.
    // A run can have zero failures but still fail because its logins are slow.
    login_load_duration: ['p(95)<3000'],
    login_load_failures: ['rate<0.01'],
  },
};

// Keycloak login and token endpoints accept URL-encoded form fields.
function formEncode(values) {
  return Object.entries(values)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
    .join('&');
}

// Build a fresh PKCE verifier for this test login, using the allowed characters.
function randomVerifier() {
  const characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~';
  let value = '';
  for (let index = 0; index < 64; index += 1) {
    value += characters[Math.floor(Math.random() * characters.length)];
  }
  return value;
}

// No setup/warm-up phase: each measured iteration executes the full login flow.
export default function () {
  // Use the scenario-wide iteration number to rotate through test accounts.
  // If a run starts more iterations than there are accounts, the list wraps.
  const account = accounts[exec.scenario.iterationInTest % accounts.length];
  const verifier = randomVerifier();
  // Send the SHA-256 challenge now; send the original verifier at token exchange.
  const challenge = encoding.b64encode(crypto.sha256(verifier, 'binary'), 'rawurl');
  const state = `${Date.now()}-${Math.random()}`;
  // Wall-clock duration covers all three HTTP steps and intervening client work.
  const startedAt = Date.now();
  let valid = true;

  // Step 1: request the authorization page and locate Keycloak's login form.
  const authorization = http.get(
    `${issuer}/protocol/openid-connect/auth?${formEncode({
      client_id: clientId,
      redirect_uri: redirectUri,
      response_type: 'code',
      scope: 'openid profile email',
      code_challenge: challenge,
      code_challenge_method: 'S256',
      state,
      nonce: `${state}-nonce`,
      // Ask for an actual login rather than relying on an existing SSO session.
      prompt: 'login',
    })}`,
    { tags: { name: 'keycloak_authorization' } },
  );
  const formAction = authorization.html().find('#kc-form-login').attr('action');
  valid = check(authorization, {
    'authorization page returned HTTP 200': (response) => response.status === 200,
    'login form was present': () => Boolean(formAction),
  }) && valid;

  let codeMatch;
  if (formAction) {
    // Step 2: submit credentials and inspect the redirect for an authorization code.
    const credentialResponse = http.post(
      formAction,
      formEncode({ username: account.username, password: account.password, credentialId: '' }),
      {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        // Do not follow the mobile deep link; read its Location header instead.
        redirects: 0,
        tags: { name: 'keycloak_credential_submission' },
      },
    );
    const location = credentialResponse.headers.Location || '';
    // Optional diagnostics redact redirect parameter values before printing.
    if (__ENV.DEBUG_REDIRECT === 'true' && !location.match(/[?&]code=/)) {
      console.log(`redirect path: ${location.replace(/=([^&]+)/g, '=<redacted>')}`);
    }
    codeMatch = location.match(/[?&]code=([^&]+)/);
    valid = check(credentialResponse, {
      'credentials produced a redirect': (response) => [302, 303].includes(response.status),
      'authorization code was returned': () => Boolean(codeMatch),
    }) && valid;
  } else {
    valid = false;
  }

  if (codeMatch) {
    // Step 3: exchange the authorization code plus PKCE verifier for tokens.
    const token = http.post(
      `${issuer}/protocol/openid-connect/token`,
      formEncode({
        grant_type: 'authorization_code',
        client_id: clientId,
        redirect_uri: redirectUri,
        code: decodeURIComponent(codeMatch[1]),
        code_verifier: verifier,
      }),
      {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        tags: { name: 'keycloak_token_exchange' },
      },
    );
    // Preserve earlier failures: successful token issuance alone is insufficient.
    valid = check(token, {
      'token exchange returned HTTP 200': (response) => response.status === 200,
      'access token was issued': (response) => Boolean(response.json('access_token')),
    }) && valid;
  } else {
    valid = false;
  }

  // Record one duration and one pass/fail sample per completed login iteration,
  // including failed attempts. Individual HTTP requests also have built-in metrics.
  // p95 means 95% of sampled login durations are at or below that value.
  loginDuration.add(Date.now() - startedAt);
  loginFailures.add(!valid);
  // No sleep: the selected executor controls the burst or arrival schedule.
  // Server/container CPU and RAM sampling is handled outside this script.
}
