import "server-only";
import { cache } from "react";
import { redirect } from "next/navigation";
import { decryptSession, deleteSession, readSessionCookie, updateSessionRefreshToken, type SessionPayload } from "./session";
import { WebRole } from "./roles";
import { getOidcDiscovery, refreshTokens, TokenResponse } from "./oidc";

// Data Access Layer: the single place session validity is checked, per Next.js's
// recommended auth pattern. decryptSession only verifies our own session cookie's
// signature — the Keycloak-issued tokens inside it were already verified once, in
// app/api/auth/callback/route.ts, via oidc.ts's verifyIdToken.
export const verifySession = cache(async (): Promise<SessionPayload | null> => {
  const cookieValue = await readSessionCookie();
  return decryptSession(cookieValue);
});

export async function requireSession(): Promise<SessionPayload> {
  const session = await verifySession();
  if (!session) {
    redirect("/login");
  }
  return session;
}

export async function requireRole(role: WebRole): Promise<SessionPayload> {
  const session = await requireSession();
  if (session.role !== role) {
    redirect(role === "administrator" ? "/lecturer/dashboard" : "/admin/dashboard");
  }
  return session;
}

export type CurrentUser = {
  name: string;
  role: WebRole;
};

export async function getCurrentUser(): Promise<CurrentUser | null> {
  const session = await verifySession();
  if (!session) return null;
  return { name: session.name, role: session.role };
}

// The session cookie only holds a refresh token (see session.ts for why access/ID
// tokens aren't persisted), so getting a usable access token always means asking
// Keycloak for one. cache() dedupes that to one refresh per request even if several
// components on the same page call this. services/*.ts (Stage 6) calls this before
// every core-backend request.
export const getValidAccessToken = cache(async (): Promise<string> => {
  const session = await requireSession();
  const tokens = await refreshOrSignOut(session);
  return tokens.accessToken;
});

async function refreshOrSignOut(session: SessionPayload): Promise<TokenResponse> {
  let tokens: TokenResponse;
  try {
    const discovery = await getOidcDiscovery();
    tokens = await refreshTokens({ discovery, refreshToken: session.refreshToken });
  } catch {
    // Refresh token expired/revoked at Keycloak — the user must sign in again.
    await deleteSession();
    redirect("/login");
  }

  try {
    // Next.js only allows cookie writes from a Server Action or Route
    // Handler. getValidAccessToken() is also called from plain Server
    // Component pages (every services/*.ts read), where this throws.
    // That's fine to swallow here: Keycloak's default (non-revoking) refresh
    // token config lets the still-cookied token be reused again next time,
    // so a request that couldn't persist the rotated token doesn't break
    // the session — it just re-rotates from the same starting point.
    await updateSessionRefreshToken(session, tokens.refreshToken);
  } catch {
    // Not writable in this render context — safe to ignore, see above.
  }

  return tokens;
}

// Used only by sign-out (app/actions/auth.ts), which needs a fresh ID token for
// Keycloak's id_token_hint but has no other reason to touch the token endpoint.
export async function getFreshIdTokenForLogout(session: SessionPayload): Promise<string | null> {
  try {
    const discovery = await getOidcDiscovery();
    const tokens = await refreshTokens({ discovery, refreshToken: session.refreshToken });
    return tokens.idToken;
  } catch {
    return null;
  }
}
