import { NextRequest, NextResponse } from "next/server";
import { exchangeCodeForTokens, getOidcDiscovery, verifyAccessToken, verifyIdToken } from "@/lib/auth/oidc";
import { readAndClearOidcFlowCookie } from "@/lib/auth/oidcFlowState";
import { createSession } from "@/lib/auth/session";
import { dashboardPathForRole, isWebRole } from "@/lib/auth/roles";
import { webUrl } from "@/lib/auth/webBaseUrl";

function loginError(request: NextRequest, code: string): NextResponse {
  return NextResponse.redirect(webUrl(`/login?error=${encodeURIComponent(code)}`, request.url));
}

export async function GET(request: NextRequest) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");
  const keycloakError = url.searchParams.get("error");

  const flow = await readAndClearOidcFlowCookie();

  if (keycloakError) {
    return loginError(request, keycloakError);
  }
  if (!code || !state || !flow || state !== flow.state) {
    return loginError(request, "invalid_state");
  }

  const discovery = await getOidcDiscovery();

  let tokens;
  try {
    tokens = await exchangeCodeForTokens({
      discovery,
      code,
      redirectUri: flow.redirectUri,
      codeVerifier: flow.codeVerifier,
    });
  } catch {
    return loginError(request, "token_exchange_failed");
  }

  let identity;
  let roles: string[];
  try {
    identity = await verifyIdToken({ discovery, idToken: tokens.idToken, expectedNonce: flow.nonce });
    roles = await verifyAccessToken({ discovery, accessToken: tokens.accessToken });
  } catch (error) {
    // Logged for operator diagnostics — jose's errors are descriptive messages only
    // (e.g. "signature verification failed"), never token contents.
    console.error("Keycloak token verification failed during login callback:", error);
    return loginError(request, "invalid_id_token");
  }

  const webRole = roles.find(isWebRole);
  if (!webRole) {
    // Students (and any account without a lecturer/administrator realm role) are
    // mobile-only — they must never reach the web dashboard.
    return loginError(request, "no_web_role");
  }

  await createSession({ userId: identity.sub, name: identity.name, role: webRole, tokens });

  return NextResponse.redirect(webUrl(dashboardPathForRole(webRole), request.url));
}
