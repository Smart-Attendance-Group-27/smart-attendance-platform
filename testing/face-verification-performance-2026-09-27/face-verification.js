import http from 'k6/http';
import { check, sleep } from 'k6';
import crypto from 'k6/crypto';
import encoding from 'k6/encoding';
import { Rate, Trend } from 'k6/metrics';

const issuer = 'https://auth.152-53-33-198.sslip.io/realms/uniattend';
const endpoint = 'https://face.152-53-33-198.sslip.io/api/v1/face-verification/readiness';
const clientId = 'uniattend-mobile';
const redirectUri = 'uniattend://auth/callback';
const imagePath = __ENV.TEST_FACE_IMAGE_PATH;

if (!imagePath) {
  throw new Error('TEST_FACE_IMAGE_PATH is required');
}

const faceImage = open(imagePath, 'b');
const verificationDuration = new Trend('face_verification_duration', true);
const requestFailures = new Rate('face_verification_request_failures');
const verificationPasses = new Rate('face_verification_passes');
let vuAccessToken;
let vuRefreshToken;
let vuExpiresAt = 0;

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
    face_verification_request_failures: ['rate==0'],
    face_verification_duration: ['p(95)<10000'],
  },
};

function formEncode(values) {
  return Object.entries(values)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
    .join('&');
}

function authenticate() {
  const verifier = __ENV.PKCE_VERIFIER;
  const username = __ENV.TEST_USERNAME;
  const password = __ENV.TEST_PASSWORD;
  if (!verifier || !username || !password) {
    throw new Error('PKCE_VERIFIER, TEST_USERNAME and TEST_PASSWORD are required');
  }

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
  const formAction = authorization.html().find('#kc-form-login').attr('action');
  if (!formAction) throw new Error('Keycloak login form was not found');

  const login = http.post(
    formAction,
    formEncode({ username, password, credentialId: '' }),
    {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      redirects: 0,
      tags: { name: 'keycloak_credential_submission' },
    },
  );
  const match = (login.headers.Location || '').match(/[?&]code=([^&]+)/);
  if (!match) throw new Error(`Keycloak credential submission failed (${login.status})`);

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

export function setup() {
  const authentication = authenticate();
  const warmups = Number(__ENV.WARMUPS || 3);
  for (let index = 0; index < warmups; index += 1) {
    const response = verify(authentication.accessToken, 'warmup_face_verification');
    if (response.status !== 200) {
      throw new Error(`Face verification warm-up failed (${response.status})`);
    }
  }
  return authentication;
}

export default function (data) {
  if (!vuAccessToken) {
    vuAccessToken = data.accessToken;
    vuRefreshToken = data.refreshToken;
    vuExpiresAt = Date.now() + data.expiresIn * 1000;
  }
  if (Date.now() >= vuExpiresAt - 30000) {
    refreshAuthentication();
  }

  const response = verify(vuAccessToken, 'measured_face_verification');
  const status = response.status === 200 ? response.json('status') : null;
  const valid = check(response, {
    'face verification returned HTTP 200': (result) => result.status === 200,
    'face verification returned a processing status': () => Boolean(status),
  });

  verificationDuration.add(response.timings.duration);
  requestFailures.add(!valid || status === 'processing_failed');
  verificationPasses.add(status === 'passed');
  sleep(0.25);
}
