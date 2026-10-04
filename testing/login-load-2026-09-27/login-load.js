import http from 'k6/http';
import { check } from 'k6';
import crypto from 'k6/crypto';
import encoding from 'k6/encoding';
import exec from 'k6/execution';
import { SharedArray } from 'k6/data';
import { Rate, Trend } from 'k6/metrics';

const issuer = 'https://auth.152-53-33-198.sslip.io/realms/uniattend';
const clientId = 'uniattend-mobile';
const redirectUri = 'uniattend://auth/callback';
const loadUsers = Number(__ENV.LOAD_USERS || 200);
const loadPattern = __ENV.LOAD_PATTERN || 'stress';

const accounts = new SharedArray('login load accounts', () => {
  const lines = open(__ENV.USERS_FILE).replace(/^\uFEFF/, '').trim().split(/\r?\n/);
  return lines.slice(1).map((line) => {
    const fields = line.split(',').map((field) => field.replace(/^"|"$/g, ''));
    return { username: fields[0], password: fields[1] };
  });
});

if (accounts.length < loadUsers) {
  throw new Error(`Need ${loadUsers} accounts but only ${accounts.length} were loaded`);
}

const loginDuration = new Trend('login_load_duration', true);
const loginFailures = new Rate('login_load_failures');

const scenario = loadPattern === 'controlled'
  ? {
      executor: 'constant-arrival-rate',
      rate: loadUsers,
      timeUnit: '1m',
      duration: '1m',
      preAllocatedVUs: Math.min(50, loadUsers),
      maxVUs: loadUsers,
      gracefulStop: '30s',
    }
  : {
      executor: 'per-vu-iterations',
      vus: loadUsers,
      iterations: 1,
      maxDuration: '5m',
      gracefulStop: '30s',
    };

export const options = {
  scenarios: { login_load: scenario },
  thresholds: {
    login_load_duration: ['p(95)<3000'],
    login_load_failures: ['rate<0.01'],
  },
};

function formEncode(values) {
  return Object.entries(values)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
    .join('&');
}

function randomVerifier() {
  const characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~';
  let value = '';
  for (let index = 0; index < 64; index += 1) {
    value += characters[Math.floor(Math.random() * characters.length)];
  }
  return value;
}

export default function () {
  const account = accounts[exec.scenario.iterationInTest % accounts.length];
  const verifier = randomVerifier();
  const challenge = encoding.b64encode(crypto.sha256(verifier, 'binary'), 'rawurl');
  const state = `${Date.now()}-${Math.random()}`;
  const startedAt = Date.now();
  let valid = true;

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
    const credentialResponse = http.post(
      formAction,
      formEncode({ username: account.username, password: account.password, credentialId: '' }),
      {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        redirects: 0,
        tags: { name: 'keycloak_credential_submission' },
      },
    );
    const location = credentialResponse.headers.Location || '';
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
    valid = check(token, {
      'token exchange returned HTTP 200': (response) => response.status === 200,
      'access token was issued': (response) => Boolean(response.json('access_token')),
    }) && valid;
  } else {
    valid = false;
  }

  loginDuration.add(Date.now() - startedAt);
  loginFailures.add(!valid);
}
