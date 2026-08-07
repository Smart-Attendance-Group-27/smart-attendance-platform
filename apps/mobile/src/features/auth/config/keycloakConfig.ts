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
  logoutRedirectPath: 'auth/logout-callback',
  scopes: [
    'openid',
    'profile',
    'email',
  ],
} as const;

export type KeycloakAuthConfig = typeof keycloakAuthConfig;

type KeycloakRedirectUriOptions = {
  readonly redirectScheme?: KeycloakAuthConfig['redirectScheme'];
  readonly redirectPath?: string;
};

export function buildKeycloakRedirectUri({
  redirectScheme = keycloakAuthConfig.redirectScheme,
  redirectPath = keycloakAuthConfig.redirectPath,
}: KeycloakRedirectUriOptions = {}) {
  return `${redirectScheme}://${redirectPath}`;
}

type KeycloakLogoutUrlOptions = {
  readonly idToken?: string;
  readonly postLogoutRedirectUri?: string;
};

export function buildKeycloakLogoutUrl({
  idToken,
  postLogoutRedirectUri,
}: KeycloakLogoutUrlOptions = {}) {
  const queryParams = new URLSearchParams({
    client_id: keycloakAuthConfig.clientId,
  });

  if (idToken) {
    queryParams.set('id_token_hint', idToken);
  }

  if (postLogoutRedirectUri) {
    queryParams.set('post_logout_redirect_uri', postLogoutRedirectUri);
  }

  return `${keycloakAuthConfig.issuerUrl}/protocol/openid-connect/logout?${queryParams.toString()}`;
}
