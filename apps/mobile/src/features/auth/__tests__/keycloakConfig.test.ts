import {
  beforeEach,
  describe,
  expect,
  test,
} from '@jest/globals';

import {
  buildKeycloakAuthConfig,
  buildKeycloakLogoutUrl,
  buildKeycloakRedirectUri,
  keycloakAuthConfig,
} from '../config/keycloakConfig';

beforeEach(() => {
  delete process.env.EXPO_PUBLIC_KEYCLOAK_BASE_URL;
  delete process.env.EXPO_PUBLIC_KEYCLOAK_CLIENT_ID;
  delete process.env.EXPO_PUBLIC_KEYCLOAK_HOST;
  delete process.env.EXPO_PUBLIC_KEYCLOAK_ISSUER_URL;
  delete process.env.EXPO_PUBLIC_KEYCLOAK_REALM;
});

describe('keycloakAuthConfig', () => {
  test('matches the local UniAttend realm and mobile client by default', () => {
    const config = buildKeycloakAuthConfig({});

    expect(config.realm).toBe('uniattend');
    expect(config.clientId).toBe('uniattend-mobile');
  });

  test('uses the Android emulator host for local Keycloak by default', () => {
    const config = buildKeycloakAuthConfig({});

    expect(config.issuerUrl).toBe(
      'http://10.0.2.2:8080/realms/uniattend',
    );
    expect(config.localIssuerUrl).toBe(
      'http://localhost:8080/realms/uniattend',
    );
  });

  test('uses a deployed shared Keycloak issuer when configured', () => {
    const config = buildKeycloakAuthConfig({
      EXPO_PUBLIC_KEYCLOAK_ISSUER_URL:
        'https://keycloak-dev.example.test/realms/uniattend-dev/',
      EXPO_PUBLIC_KEYCLOAK_REALM: 'uniattend-dev',
    });

    expect(config.realm).toBe('uniattend-dev');
    expect(config.clientId).toBe('uniattend-mobile');
    expect(config.issuerUrl).toBe(
      'https://keycloak-dev.example.test/realms/uniattend-dev',
    );
  });

  test('builds the issuer from a deployed base url and URL-encodes the realm', () => {
    const config = buildKeycloakAuthConfig({
      EXPO_PUBLIC_KEYCLOAK_BASE_URL:
        'https://keycloak-production-be79.up.railway.app/',
      EXPO_PUBLIC_KEYCLOAK_REALM: 'Uni Attend',
    });

    expect(config.issuerUrl).toBe(
      'https://keycloak-production-be79.up.railway.app/realms/Uni%20Attend',
    );
  });

  test('builds a redirect uri accepted by the mobile Keycloak client', () => {
    expect(buildKeycloakRedirectUri()).toBe('uniattend://auth/callback');
  });

  test('builds a logout redirect uri accepted by the mobile Keycloak client', () => {
    expect(
      buildKeycloakRedirectUri({
        redirectPath: keycloakAuthConfig.logoutRedirectPath,
      }),
    ).toBe('uniattend://auth/logout-callback');
  });

  test('builds the Keycloak RP-initiated logout url', () => {
    expect(
      buildKeycloakLogoutUrl({
        idToken: 'sample-id-token',
        postLogoutRedirectUri: 'uniattend://auth/logout-callback',
      }),
    ).toBe(
      'http://10.0.2.2:8080/realms/uniattend/protocol/openid-connect/logout?client_id=uniattend-mobile&id_token_hint=sample-id-token&post_logout_redirect_uri=uniattend%3A%2F%2Fauth%2Flogout-callback',
    );
  });

  test('builds logout against the configured shared issuer', () => {
    const sharedConfig = buildKeycloakAuthConfig({
      EXPO_PUBLIC_KEYCLOAK_ISSUER_URL:
        'https://keycloak-dev.example.test/realms/uniattend-dev',
    });

    expect(buildKeycloakLogoutUrl({ config: sharedConfig })).toBe(
      'https://keycloak-dev.example.test/realms/uniattend-dev/protocol/openid-connect/logout?client_id=uniattend-mobile',
    );
  });
});
