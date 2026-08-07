import {
  describe,
  expect,
  test,
} from '@jest/globals';

import {
  buildKeycloakRedirectUri,
  keycloakAuthConfig,
} from '../config/keycloakConfig';

describe('keycloakAuthConfig', () => {
  test('matches the local UniAttend realm and mobile client', () => {
    expect(keycloakAuthConfig.realm).toBe('uniattend');
    expect(keycloakAuthConfig.clientId).toBe('uniattend-mobile');
  });

  test('uses the Android emulator host for local Keycloak by default', () => {
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
});
