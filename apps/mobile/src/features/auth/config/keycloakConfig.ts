const keycloakRealm = 'uniattend';
const keycloakLocalPort = 8080;
const defaultAndroidEmulatorHost = '10.0.2.2';

const buildLocalIssuerUrl = (host: string) =>
  `http://${host}:${keycloakLocalPort}/realms/${keycloakRealm}`;

const keycloakHost =
  process.env.EXPO_PUBLIC_KEYCLOAK_HOST?.trim() || defaultAndroidEmulatorHost;

export const keycloakAuthConfig = {
  realm: keycloakRealm,
  clientId: 'uniattend-mobile',
  issuerUrl: buildLocalIssuerUrl(keycloakHost),
  localIssuerUrl: buildLocalIssuerUrl('localhost'),
  redirectScheme: 'uniattend',
  redirectPath: 'auth/callback',
  scopes: [
    'openid',
    'profile',
    'email',
  ],
} as const;

export type KeycloakAuthConfig = typeof keycloakAuthConfig;

export function buildKeycloakRedirectUri({
  redirectScheme,
  redirectPath,
}: Pick<KeycloakAuthConfig, 'redirectScheme' | 'redirectPath'> = keycloakAuthConfig) {
  return `${redirectScheme}://${redirectPath}`;
}
