const defaultKeycloakRealm = 'uniattend';
const defaultKeycloakClientId = 'uniattend-mobile';
const keycloakLocalPort = 8080;
const defaultAndroidEmulatorHost = '10.0.2.2';

const stripTrailingSlash = (value: string) => value.replace(/\/+$/, '');

type KeycloakPublicEnv = Record<string, string | undefined> & {
  readonly EXPO_PUBLIC_KEYCLOAK_BASE_URL?: string;
  readonly EXPO_PUBLIC_KEYCLOAK_CLIENT_ID?: string;
  readonly EXPO_PUBLIC_KEYCLOAK_HOST?: string;
  readonly EXPO_PUBLIC_KEYCLOAK_ISSUER_URL?: string;
  readonly EXPO_PUBLIC_KEYCLOAK_REALM?: string;
};

const readPublicEnv = (env: KeycloakPublicEnv, name: keyof KeycloakPublicEnv) =>
  env[name]?.trim() || undefined;

const buildIssuerUrl = (baseUrl: string, realm: string) =>
  `${baseUrl}/realms/${encodeURIComponent(realm)}`;

export function buildKeycloakAuthConfig(env: KeycloakPublicEnv = process.env) {
  const keycloakRealm =
    readPublicEnv(env, 'EXPO_PUBLIC_KEYCLOAK_REALM') || defaultKeycloakRealm;

  const keycloakClientId =
    readPublicEnv(env, 'EXPO_PUBLIC_KEYCLOAK_CLIENT_ID') ||
    defaultKeycloakClientId;

  const keycloakHost =
    readPublicEnv(env, 'EXPO_PUBLIC_KEYCLOAK_HOST') ||
    defaultAndroidEmulatorHost;

  const keycloakBaseUrl = stripTrailingSlash(
    readPublicEnv(env, 'EXPO_PUBLIC_KEYCLOAK_BASE_URL') ||
      `http://${keycloakHost}:${keycloakLocalPort}`,
  );

  const issuerUrl = stripTrailingSlash(
    readPublicEnv(env, 'EXPO_PUBLIC_KEYCLOAK_ISSUER_URL') ||
      buildIssuerUrl(keycloakBaseUrl, keycloakRealm),
  );

  return {
    realm: keycloakRealm,
    clientId: keycloakClientId,
    issuerUrl,
    localIssuerUrl: buildIssuerUrl(
      `http://localhost:${keycloakLocalPort}`,
      keycloakRealm,
    ),
    redirectScheme: 'uniattend',
    redirectPath: 'auth/callback',
    logoutRedirectPath: 'auth/logout-callback',
    scopes: [
      'openid',
      'profile',
      'email',
    ],
  } as const;
}

export const keycloakAuthConfig = buildKeycloakAuthConfig();

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
  readonly config?: KeycloakAuthConfig;
  readonly idToken?: string;
  readonly postLogoutRedirectUri?: string;
};

export function buildKeycloakLogoutUrl({
  config = keycloakAuthConfig,
  idToken,
  postLogoutRedirectUri,
}: KeycloakLogoutUrlOptions = {}) {
  const queryParams = new URLSearchParams({
    client_id: config.clientId,
  });

  if (idToken) {
    queryParams.set('id_token_hint', idToken);
  }

  if (postLogoutRedirectUri) {
    queryParams.set('post_logout_redirect_uri', postLogoutRedirectUri);
  }

  return `${config.issuerUrl}/protocol/openid-connect/logout?${queryParams.toString()}`;
}
