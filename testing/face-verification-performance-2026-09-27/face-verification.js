import http from 'k6/http';
import { check, sleep } from 'k6';
import crypto from 'k6/crypto';
import encoding from 'k6/encoding';
import { Rate, Trend } from 'k6/metrics';

// Face-readiness image-verification performance test (includes model inference).
// Flow: sign in -> warm up -> repeat authenticated photo uploads -> record metrics.
// The same photo and account are reused; this measures API performance rather
// than the phone camera/liveness UI or face accuracy across different people.
const issuer = 'https://auth.152-53-33-198.sslip.io/realms/uniattend';
const endpoint = 'https://face.152-53-33-198.sslip.io/api/v1/face-verification/readiness';
const clientId = 'uniattend-mobile';
const redirectUri = 'uniattend://auth/callback';
// Supply the image, credentials and PKCE verifier through environment variables.
const imagePath = __ENV.TEST_FACE_IMAGE_PATH;

if (!imagePath) {
  throw new Error('TEST_FACE_IMAGE_PATH is required');
}

// k6 loads the image once during initialization, rather than reading it each scan.
const faceImage = open(imagePath, 'b');
// Trend stores response-time samples in milliseconds for average/median/p95.
// Rate stores the fraction of samples for which the supplied value is true.
const verificationDuration = new Trend('face_verification_duration', true);
const requestFailures = new Rate('face_verification_request_failures');
const verificationPasses = new Rate('face_verification_passes');
let vuAccessToken;
let vuRefreshToken;
let vuExpiresAt = 0;

// One virtual user (VU) performs 200 sequential iterations by default.
// This establishes a single-user baseline; it does not measure concurrency.
export const options = {
  scenarios: {
    face_verification: {
      executor: 'shared-iterations',
      vus: 1,
      iterations: Number(__ENV.ITERATIONS || 200),
      maxDuration: '30m',
    },
  },
  thresholds: {
    // Fail the run if any measured request fails or p95 reaches 10 seconds.
    // p95 is the response time at or below which 95% of samples fall.
    face_verification_request_failures: ['rate==0'],
    face_verification_duration: ['p(95)<10000'],
  },
};

// Keycloak expects URL-encoded form fields for login and token requests.
function formEncode(values) {
  return Object.entries(values)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
    .join('&');
}

// Follow the mobile client's authorization-code-with-PKCE login flow.
function authenticate() {
  const verifier = __ENV.PKCE_VERIFIER;
  const username = __ENV.TEST_USERNAME;
  const password = __ENV.TEST_PASSWORD;
  if (!verifier || !username || !password) {
    throw new Error('PKCE_VERIFIER, TEST_USERNAME and TEST_PASSWORD are required');
  }

  // PKCE sends a SHA-256 challenge first and the original verifier at exchange.
  const challenge = encoding.b64encode(crypto.sha256(verifier, 'binary'), 'rawurl');
  const state = `${Date.now()}-${Math.random()}`;
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
    })}`,
    { tags: { name: 'keycloak_authorization' } },
  );
  // Read Keycloak's actual form action, then submit the test account credentials.
  const formAction = authorization.html().find('#kc-form-login').attr('action');
  if (!formAction) throw new Error('Keycloak login form was not found');

  const login = http.post(
    formAction,
    formEncode({ username, password, credentialId: '' }),
    {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      // Keep the redirect response so we can extract its authorization code.
      redirects: 0,
      tags: { name: 'keycloak_credential_submission' },
    },
  );
  const match = (login.headers.Location || '').match(/[?&]code=([^&]+)/);
  if (!match) throw new Error(`Keycloak credential submission failed (${login.status})`);

  // Exchange the short-lived authorization code for access and refresh tokens.
  const token = http.post(
    `${issuer}/protocol/openid-connect/token`,
    formEncode({
      grant_type: 'authorization_code',
      client_id: clientId,
      redirect_uri: redirectUri,
      code: decodeURIComponent(match[1]),
      code_verifier: verifier,
    }),
    {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      tags: { name: 'keycloak_token_exchange' },
    },
  );
  if (token.status !== 200 || !token.json('access_token')) {
    throw new Error(`Keycloak token exchange failed (${token.status})`);
  }
  return {
    accessToken: token.json('access_token'),
    refreshToken: token.json('refresh_token'),
    expiresIn: Number(token.json('expires_in') || 300),
  };
}

// Refresh expired/expiring access credentials without repeating browser login.
function refreshAuthentication() {
  const token = http.post(
    `${issuer}/protocol/openid-connect/token`,
    formEncode({
      grant_type: 'refresh_token',
      client_id: clientId,
      refresh_token: vuRefreshToken,
    }),
    {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      tags: { name: 'keycloak_token_refresh' },
    },
  );
  if (token.status !== 200 || !token.json('access_token')) {
    throw new Error(`Keycloak token refresh failed (${token.status})`);
  }
  vuAccessToken = token.json('access_token');
  vuRefreshToken = token.json('refresh_token') || vuRefreshToken;
  vuExpiresAt = Date.now() + Number(token.json('expires_in') || 300) * 1000;
}

// Send the photo as multipart/form-data, authenticated with the student's token.
// The request name tag separates warm-up calls from measured calls in k6 output.
function verify(accessToken, name) {
  return http.post(
    endpoint,
    { image: http.file(faceImage, 'face-performance-input.jpeg', 'image/jpeg') },
    {
      headers: { Authorization: `Bearer ${accessToken}` },
      tags: { name },
      timeout: '30s',
    },
  );
}

// setup() runs once before the measured iterations and returns their login data.
export function setup() {
  const authentication = authenticate();
  // Exercise the endpoint three times by default before collecting custom metrics.
  // Warm-up checks HTTP success; the measured loop separately records match passes.
  const warmups = Number(__ENV.WARMUPS || 3);
  for (let index = 0; index < warmups; index += 1) {
    const response = verify(authentication.accessToken, 'warmup_face_verification');
    if (response.status !== 200) {
      throw new Error(`Face verification warm-up failed (${response.status})`);
    }
  }
  return authentication;
}

// k6 repeats this function once per iteration: one face-verification request.
export default function (data) {
  // Each VU keeps its own token state, initialized from setup()'s returned data.
  if (!vuAccessToken) {
    vuAccessToken = data.accessToken;
    vuRefreshToken = data.refreshToken;
    vuExpiresAt = Date.now() + data.expiresIn * 1000;
  }
  // Refresh 30 seconds early to avoid authentication expiry during an upload.
  if (Date.now() >= vuExpiresAt - 30000) {
    refreshAuthentication();
  }

  const response = verify(vuAccessToken, 'measured_face_verification');
  const status = response.status === 200 ? response.json('status') : null;
  // An HTTP 200 with a status means the endpoint responded; it need not be a match.
  const valid = check(response, {
    'face verification returned HTTP 200': (result) => result.status === 200,
    'face verification returned a processing status': () => Boolean(status),
  });

  // Only measured photo requests enter these custom metrics. Built-in HTTP
  // metrics also include authentication and warm-ups. Duration includes request
  // sending, server wait and response receiving, but excludes connection setup.
  verificationDuration.add(response.timings.duration);
  requestFailures.add(!valid || status === 'processing_failed');
  // Match success is reported separately; no pass-rate threshold is configured.
  verificationPasses.add(status === 'passed');
  // Pause between requests; this is not included in verificationDuration.
  // Host/container CPU and RAM sampling is handled outside this script.
  sleep(0.25);
}
