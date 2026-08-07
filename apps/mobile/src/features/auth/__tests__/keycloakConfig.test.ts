import {
  describe,
  expect,
  test,
} from '@jest/globals';

import {
  buildKeycloakLogoutUrl,
  buildKeycloakRedirectUri,
  keycloakAuthConfig,
} from '../config/keycloakConfig';

describe('keycloakAuthConfig', () => {
  test('matches the local UniAttend realm and mobile client', () => {
    expect(keycloakAuthConfig.realm).toBe('uniattend');
    expect(keycloakAuthConfig.clientId).toBe('uniattend-mobile');
  });

  test('uses the Android emulator host for local Keycloak', () => {
    expect(keycloakAuthConfig.issuerUrl).toBe(
      'http://10.0.2.2:8080/realms/uniattend',
    );
    expect(keycloakAuthConfig.localIssuerUrl).toBe(
      'http://localhost:8080/realms/uniattend',
    );
  });

  test('builds a redirect uri accepted by the local Keycloak realm', () => {
    expect(buildKeycloakRedirectUri()).toBe('uniattend://auth/callback');
  });

  test('builds a logout redirect uri accepted by the local Keycloak realm', () => {
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
});
