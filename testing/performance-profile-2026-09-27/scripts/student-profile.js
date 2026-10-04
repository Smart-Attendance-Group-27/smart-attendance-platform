import http from 'k6/http';
import { check, sleep } from 'k6';
import crypto from 'k6/crypto';
import encoding from 'k6/encoding';
import { Rate, Trend } from 'k6/metrics';

const issuer = 'https://auth.152-53-33-198.sslip.io/realms/uniattend';
const apiBaseUrl = 'https://api.152-53-33-198.sslip.io/api/v1';
const clientId = 'uniattend-mobile';
const redirectUri = 'uniattend://auth/callback';

const profileDuration = new Trend('student_profile_duration', true);
const profileFailures = new Rate('student_profile_failures');

export const options = {
  scenarios: {
    student_profile: {
      executor: 'shared-iterations',
      vus: 1,
      iterations: 200,
      maxDuration: '5m',
    },
  },
  thresholds: {
    student_profile_duration: ['p(95)<1500'],
    student_profile_failures: ['rate==0'],
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
  const authorizationUrl = `${issuer}/protocol/openid-connect/auth?${formEncode({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: 'code',
    scope: 'openid profile email',
    code_challenge: challenge,
    code_challenge_method: 'S256',
    state,
    nonce: `${state}-nonce`,
  })}`;

  const authorization = http.get(authorizationUrl, {
    tags: { name: 'keycloak_authorization' },
  });
  const formAction = authorization.html().find('#kc-form-login').attr('action');
  if (!formAction) {
    throw new Error(`Keycloak login form was not found (status ${authorization.status})`);
  }

  const login = http.post(
    formAction,
    formEncode({ username, password, credentialId: '' }),
    {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      redirects: 0,
      tags: { name: 'keycloak_credential_submission' },
    },
  );
  const location = login.headers.Location || '';
  const codeMatch = location.match(/[?&]code=([^&]+)/);
  if (!codeMatch) {
    throw new Error(`Keycloak credential submission failed (status ${login.status})`);
  }

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
  if (token.status !== 200 || !token.json('access_token')) {
    throw new Error(`Keycloak token exchange failed (status ${token.status})`);
  }
  return token.json('access_token');
}

export function setup() {
  const accessToken = authenticate();
  const params = { headers: { Authorization: `Bearer ${accessToken}` } };
  for (let index = 0; index < 3; index += 1) {
    const warmup = http.get(`${apiBaseUrl}/students/me/profile`, {
      ...params,
      tags: { name: 'warmup_student_profile' },
    });
    if (warmup.status !== 200) {
      throw new Error(`Student profile warm-up failed (status ${warmup.status})`);
    }
  }
  return { accessToken };
}

export default function (data) {
  const response = http.get(`${apiBaseUrl}/students/me/profile`, {
    headers: { Authorization: `Bearer ${data.accessToken}` },
    tags: { measured_transaction: 'student_profile', name: 'student_profile' },
  });
  const valid = check(response, {
    'student profile returned HTTP 200': (result) => result.status === 200,
    'student profile contains a registration number': (result) =>
      Boolean(result.json('registrationNumber')),
  });
  profileDuration.add(response.timings.duration);
  profileFailures.add(!valid);
  sleep(0.5);
}
