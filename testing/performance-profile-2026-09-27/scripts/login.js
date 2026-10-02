import http from 'k6/http';
import { check, sleep } from 'k6';
import crypto from 'k6/crypto';
import encoding from 'k6/encoding';
import { Rate, Trend } from 'k6/metrics';

const issuer = 'https://auth.152-53-33-198.sslip.io/realms/uniattend';
const clientId = 'uniattend-mobile';
const redirectUri = 'uniattend://auth/callback';

const loginDuration = new Trend('login_duration', true);
const loginFailures = new Rate('login_failures');

export const options = {
  scenarios: {
    login: {
      executor: 'shared-iterations',
      vus: 1,
      iterations: 200,
      maxDuration: '8m',
    },
  },
  thresholds: {
    login_duration: ['p(95)<3000'],
    login_failures: ['rate==0'],
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
  const username = __ENV.TEST_USERNAME;
  const password = __ENV.TEST_PASSWORD;
  if (!username || !password) {
    throw new Error('TEST_USERNAME and TEST_PASSWORD are required');
  }

  const startedAt = Date.now();
  const verifier = randomVerifier();
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
    prompt: 'login',
  })}`;

  const authorization = http.get(authorizationUrl, {
    tags: { login_step: 'authorization', name: 'keycloak_authorization' },
  });
  const formAction = authorization.html().find('#kc-form-login').attr('action');
  let valid = check(authorization, {
    'login page returned HTTP 200': (response) => response.status === 200,
    'login form was present': () => Boolean(formAction),
  });

  let login;
  let codeMatch;
  if (formAction) {
    login = http.post(
      formAction,
      formEncode({ username, password, credentialId: '' }),
      {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        redirects: 0,
        tags: { login_step: 'credentials', name: 'keycloak_credential_submission' },
      },
    );
    const location = login.headers.Location || '';
    codeMatch = location.match(/[?&]code=([^&]+)/);
    valid = check(login, {
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
        tags: { login_step: 'token', name: 'keycloak_token_exchange' },
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
  sleep(0.5);
}
