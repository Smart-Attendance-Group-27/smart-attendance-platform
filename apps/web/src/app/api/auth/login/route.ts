import { NextRequest, NextResponse } from "next/server";
import { buildAuthorizationUrl, generatePkcePair, generateRandomToken, getOidcDiscovery, isKeycloakConfigured } from "@/lib/auth/oidc";
import { createOidcFlowCookie } from "@/lib/auth/oidcFlowState";

export async function GET(request: NextRequest) {
  if (!isKeycloakConfigured()) {
    return NextResponse.json(
      { error: "Keycloak is not configured on this server (KEYCLOAK_ISSUER/CLIENT_ID/CLIENT_SECRET)." },
      { status: 503 },
    );
  }

  const webBaseUrl = process.env.WEB_BASE_URL ?? new URL(request.url).origin;
  const redirectUri = `${webBaseUrl}/api/auth/callback`;

  const discovery = await getOidcDiscovery();
  const { codeVerifier, codeChallenge } = generatePkcePair();
  const state = generateRandomToken();
  const nonce = generateRandomToken();

  await createOidcFlowCookie({ state, nonce, codeVerifier, redirectUri });

  const authorizationUrl = buildAuthorizationUrl({ discovery, redirectUri, state, nonce, codeChallenge });

  return NextResponse.redirect(authorizationUrl);
}
