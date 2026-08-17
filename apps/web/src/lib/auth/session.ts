import "server-only";
import { SignJWT, jwtVerify } from "jose";
import { cookies } from "next/headers";
import { WebRole } from "./roles";
import { TokenResponse } from "./oidc";

const SESSION_COOKIE_NAME = "uniattend_web_session";
const MAX_SESSION_DURATION_MS = 12 * 60 * 60 * 1000;

function encodedSecretKey(): Uint8Array {
  const secretKey = process.env.SESSION_SECRET;
  if (!secretKey && process.env.NODE_ENV === "production") {
    throw new Error("SESSION_SECRET must be set in production.");
  }
  return new TextEncoder().encode(secretKey ?? "development-only-insecure-secret");
}

export type SessionPayload = {
  userId: string; // Keycloak 'sub'
  name: string;
  role: WebRole;
  // Only the refresh token is persisted — NOT access/ID tokens. A real Keycloak
  // access+refresh+ID token set together is ~3.4KB raw, and once wrapped in this
  // cookie's own outer JWT (base64 over already-base64 JWTs, ~1.33x) exceeds the
  // ~4096-byte cookie limit and gets silently dropped by the browser (confirmed
  // against a real local Keycloak while building this). getValidAccessToken()
  // (dal.ts) derives a fresh access token from this refresh token on demand;
  // sign-out (app/actions/auth.ts) does the same for a fresh ID token.
  refreshToken: string;
  expiresAt: string;
};

export async function encryptSession(payload: SessionPayload): Promise<string> {
  return new SignJWT(payload)
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime(new Date(payload.expiresAt))
    .sign(encodedSecretKey());
}

export async function decryptSession(token: string | undefined): Promise<SessionPayload | null> {
  if (!token) return null;

  try {
    const { payload } = await jwtVerify(token, encodedSecretKey(), { algorithms: ["HS256"] });
    return payload as unknown as SessionPayload;
  } catch {
    return null;
  }
}

async function setSessionCookie(payload: SessionPayload): Promise<void> {
  const session = await encryptSession(payload);
  const cookieStore = await cookies();

  cookieStore.set(SESSION_COOKIE_NAME, session, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    expires: new Date(payload.expiresAt),
    sameSite: "lax",
    path: "/",
  });
}

export async function createSession(params: {
  userId: string;
  name: string;
  role: WebRole;
  tokens: TokenResponse;
}): Promise<void> {
  const boundedRefreshMs = Math.min(params.tokens.refreshExpiresInSeconds * 1000, MAX_SESSION_DURATION_MS);
  const expiresAt = new Date(Date.now() + boundedRefreshMs);

  await setSessionCookie({
    userId: params.userId,
    name: params.name,
    role: params.role,
    refreshToken: params.tokens.refreshToken,
    expiresAt: expiresAt.toISOString(),
  });
}

// Called after a silent token refresh (lib/auth/dal.ts) — Keycloak issues a new
// refresh token string on every use, so the cookie should be updated to carry
// it forward. This realm's default config doesn't revoke the previous token on
// rotation, so a call site that can't write cookies right now (e.g. a Server
// Component render — see dal.ts's refreshOrSignOut) can safely skip this and
// let the still-cookied token be reused next time instead of breaking the
// session; only production realms with revokeRefreshToken enabled would need
// every rotation persisted without exception.

export async function updateSessionRefreshToken(current: SessionPayload, refreshToken: string): Promise<void> {
  await setSessionCookie({ ...current, refreshToken });
}

export async function readSessionCookie(): Promise<string | undefined> {
  const cookieStore = await cookies();
  return cookieStore.get(SESSION_COOKIE_NAME)?.value;
}

export async function deleteSession(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete(SESSION_COOKIE_NAME);
}

export { SESSION_COOKIE_NAME };
