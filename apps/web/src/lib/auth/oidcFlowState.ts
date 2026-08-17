import "server-only";
import { SignJWT, jwtVerify } from "jose";
import { cookies } from "next/headers";

// Short-lived, separate from the real session cookie (session.ts) — holds only the
// per-login-attempt state/nonce/PKCE verifier between GET /api/auth/login and
// GET /api/auth/callback, then is deleted. Signed (not just httpOnly) so a tampered
// state/nonce can't be used to defeat the CSRF/replay checks it exists to enforce.

const FLOW_COOKIE_NAME = "uniattend_web_oidc_flow";
const FLOW_TTL_SECONDS = 10 * 60;

function encodedSecretKey(): Uint8Array {
  const secretKey = process.env.SESSION_SECRET;
  return new TextEncoder().encode(secretKey ?? "development-only-insecure-secret");
}

export type OidcFlowState = {
  state: string;
  nonce: string;
  codeVerifier: string;
  redirectUri: string;
};

export async function createOidcFlowCookie(flow: OidcFlowState): Promise<void> {
  const token = await new SignJWT(flow)
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime(`${FLOW_TTL_SECONDS}s`)
    .sign(encodedSecretKey());

  const cookieStore = await cookies();
  cookieStore.set(FLOW_COOKIE_NAME, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: FLOW_TTL_SECONDS,
  });
}

export async function readAndClearOidcFlowCookie(): Promise<OidcFlowState | null> {
  const cookieStore = await cookies();
  const token = cookieStore.get(FLOW_COOKIE_NAME)?.value;
  cookieStore.delete(FLOW_COOKIE_NAME);
  if (!token) return null;

  try {
    const { payload } = await jwtVerify(token, encodedSecretKey(), { algorithms: ["HS256"] });
    return payload as unknown as OidcFlowState;
  } catch {
    return null;
  }
}
