import "server-only";
import { createHash, randomBytes } from "node:crypto";
import { createRemoteJWKSet, jwtVerify, JWTPayload } from "jose";

// Real Keycloak OIDC client for the "uniattend-web" confidential client (see
// infra/local/keycloak/realm/uniattend-realm.json). Mirrors the security properties
// apps/mobile/src/features/auth already relies on (Authorization Code + PKCE, issuer/
// audience/expiry validation) but server-side, since this is a confidential client —
// the client secret must never reach the browser.

// Read lazily (not cached at module scope) so tests can set process.env after this
// module is imported, and so a long-lived process always reflects the current env.
export function isKeycloakConfigured(): boolean {
  return Boolean(process.env.KEYCLOAK_ISSUER && process.env.KEYCLOAK_CLIENT_ID && process.env.KEYCLOAK_CLIENT_SECRET);
}

function requireConfig() {
  const issuer = process.env.KEYCLOAK_ISSUER;
  const clientId = process.env.KEYCLOAK_CLIENT_ID;
  const clientSecret = process.env.KEYCLOAK_CLIENT_SECRET;
  if (!issuer || !clientId || !clientSecret) {
    throw new Error(
      "Keycloak is not configured: set KEYCLOAK_ISSUER, KEYCLOAK_CLIENT_ID, KEYCLOAK_CLIENT_SECRET.",
    );
  }
  return { issuer, clientId, clientSecret };
}

export type OidcDiscovery = {
  issuer: string;
  authorizationEndpoint: string;
  tokenEndpoint: string;
  endSessionEndpoint: string;
  jwksUri: string;
};

// No caching: the login/callback/logout round trip happens once per session, not on a
// hot path, so an extra discovery fetch per flow is simpler and safer than staleness.
export async function getOidcDiscovery(): Promise<OidcDiscovery> {
  const { issuer } = requireConfig();
  const internalIssuer = process.env.KEYCLOAK_INTERNAL_ISSUER ?? issuer;
  const response = await fetch(`${internalIssuer}/.well-known/openid-configuration`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to fetch Keycloak discovery document (${response.status}).`);
  }
  const doc = (await response.json()) as Record<string, unknown>;

  const authorizationEndpoint = String(doc.authorization_endpoint).replace(internalIssuer, issuer);
  const endSessionEndpoint = String(doc.end_session_endpoint).replace(internalIssuer, issuer);

  return {
    issuer,
    authorizationEndpoint,
    tokenEndpoint: String(doc.token_endpoint),
    endSessionEndpoint,
    jwksUri: String(doc.jwks_uri),
  };
}

export type PkcePair = { codeVerifier: string; codeChallenge: string };

function base64url(input: Buffer): string {
  return input.toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function generatePkcePair(): PkcePair {
  const codeVerifier = base64url(randomBytes(32));
  const codeChallenge = base64url(createHash("sha256").update(codeVerifier).digest());
  return { codeVerifier, codeChallenge };
}

export function generateRandomToken(): string {
  return base64url(randomBytes(16));
}

export function buildAuthorizationUrl(params: {
  discovery: OidcDiscovery;
  redirectUri: string;
  state: string;
  nonce: string;
  codeChallenge: string;
}): string {
  const { clientId } = requireConfig();
  const url = new URL(params.discovery.authorizationEndpoint);
  url.searchParams.set("client_id", clientId);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("scope", "openid profile email");
  url.searchParams.set("redirect_uri", params.redirectUri);
  url.searchParams.set("state", params.state);
  url.searchParams.set("nonce", params.nonce);
  url.searchParams.set("code_challenge", params.codeChallenge);
  url.searchParams.set("code_challenge_method", "S256");
  return url.toString();
}

export type TokenResponse = {
  accessToken: string;
  refreshToken: string;
  idToken: string;
  accessTokenExpiresAt: string;
  refreshExpiresInSeconds: number;
};

async function requestTokens(tokenEndpoint: string, body: URLSearchParams): Promise<TokenResponse> {
  const { clientId, clientSecret } = requireConfig();
  body.set("client_id", clientId);
  body.set("client_secret", clientSecret);

  const response = await fetch(tokenEndpoint, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Keycloak token endpoint returned ${response.status}.`);
  }

  const payload = (await response.json()) as {
    access_token: string;
    refresh_token: string;
    id_token: string;
    expires_in: number;
    refresh_expires_in?: number;
  };

  return {
    accessToken: payload.access_token,
    refreshToken: payload.refresh_token,
    idToken: payload.id_token,
    accessTokenExpiresAt: new Date(Date.now() + payload.expires_in * 1000).toISOString(),
    // Keycloak omits refresh_expires_in when the realm's SSO session is "remember me"/
    // non-expiring; fall back to the same bound the local session cookie itself uses.
    refreshExpiresInSeconds: payload.refresh_expires_in ?? 12 * 60 * 60,
  };
}

export async function exchangeCodeForTokens(params: {
  discovery: OidcDiscovery;
  code: string;
  redirectUri: string;
  codeVerifier: string;
}): Promise<TokenResponse> {
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    code: params.code,
    redirect_uri: params.redirectUri,
    code_verifier: params.codeVerifier,
  });
  return requestTokens(params.discovery.tokenEndpoint, body);
}

export async function refreshTokens(params: {
  discovery: OidcDiscovery;
  refreshToken: string;
}): Promise<TokenResponse> {
  const body = new URLSearchParams({ grant_type: "refresh_token", refresh_token: params.refreshToken });
  return requestTokens(params.discovery.tokenEndpoint, body);
}

export type VerifiedIdentity = {
  sub: string;
  name: string;
  email: string | undefined;
};

// Verifies signature (via Keycloak's published JWKS), issuer, audience (this client's
// own ID — the standard OIDC audience for an ID token), expiry, and nonce. Proves who
// just authenticated and that this callback belongs to the login attempt we started.
export async function verifyIdToken(params: {
  discovery: OidcDiscovery;
  idToken: string;
  expectedNonce: string;
}): Promise<VerifiedIdentity> {
  const { clientId } = requireConfig();
  const jwks = createRemoteJWKSet(new URL(params.discovery.jwksUri));

  const { payload } = await jwtVerify(params.idToken, jwks, {
    issuer: params.discovery.issuer,
    audience: clientId,
  });

  if (payload.nonce !== params.expectedNonce) {
    throw new Error("ID token nonce does not match the expected value.");
  }

  const claims = payload as JWTPayload & {
    preferred_username?: string;
    name?: string;
    email?: string;
  };

  if (!claims.sub) {
    throw new Error("ID token is missing a subject claim.");
  }

  return {
    sub: claims.sub,
    name: claims.name ?? claims.preferred_username ?? claims.email ?? claims.sub,
    email: claims.email,
  };
}

// The audience services/core-backend/modules/identity/auth/token_verifier.py expects
// (KEYCLOAK_AUDIENCE, default "uniattend-api") — the same value the uniattend-web
// client's "uniattend-api-audience" protocol mapper stamps onto its access tokens.
const CORE_BACKEND_AUDIENCE = "uniattend-api";

// Verifies the access token this app will also send to core-backend, and reads the
// realm roles it carries. Keycloak's realm-roles mapper only stamps roles onto the
// access token by default (roles are authorization data, not identity data) — the ID
// token verified above deliberately does not carry them.
export async function verifyAccessToken(params: {
  discovery: OidcDiscovery;
  accessToken: string;
}): Promise<string[]> {
  const jwks = createRemoteJWKSet(new URL(params.discovery.jwksUri));

  const { payload } = await jwtVerify(params.accessToken, jwks, {
    issuer: params.discovery.issuer,
    audience: CORE_BACKEND_AUDIENCE,
  });

  const claims = payload as JWTPayload & { realm_access?: { roles?: string[] } };
  return claims.realm_access?.roles ?? [];
}

export function buildEndSessionUrl(params: {
  discovery: OidcDiscovery;
  idTokenHint: string;
  postLogoutRedirectUri: string;
}): string {
  const { clientId } = requireConfig();
  const url = new URL(params.discovery.endSessionEndpoint);
  url.searchParams.set("client_id", clientId);
  url.searchParams.set("id_token_hint", params.idTokenHint);
  url.searchParams.set("post_logout_redirect_uri", params.postLogoutRedirectUri);
  return url.toString();
}
