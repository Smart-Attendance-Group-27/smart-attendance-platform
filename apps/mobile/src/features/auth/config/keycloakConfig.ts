const keycloakRealm = 'uniattend';
const keycloakLocalPort = 8080;

const buildLocalIssuerUrl = (host: string) =>
  `http://${host}:${keycloakLocalPort}/realms/${keycloakRealm}`;

export const keycloakAuthConfig = {
  realm: keycloakRealm,
  clientId: 'uniattend-mobile',
  issuerUrl: buildLocalIssuerUrl('10.0.2.2'),
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
