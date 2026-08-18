import { NextRequest, NextResponse } from "next/server";
import { buildAuthorizationUrl, generatePkcePair, generateRandomToken, getOidcDiscovery, isKeycloakConfigured } from "@/lib/auth/oidc";
import { createOidcFlowCookie } from "@/lib/auth/oidcFlowState";
import { getWebBaseUrl } from "@/lib/auth/webBaseUrl";

export async function GET(request: NextRequest) {
  if (!isKeycloakConfigured()) {
    return NextResponse.json(
      { error: "Keycloak is not configured on this server (KEYCLOAK_ISSUER/CLIENT_ID/CLIENT_SECRET)." },
      { status: 503 },
    );
  }

  try {
    const webBaseUrl = getWebBaseUrl(request.url);
    const redirectUri = `${webBaseUrl}/api/auth/callback`;

    const discovery = await getOidcDiscovery();
    const { codeVerifier, codeChallenge } = generatePkcePair();
    const state = generateRandomToken();
    const nonce = generateRandomToken();

    await createOidcFlowCookie({ state, nonce, codeVerifier, redirectUri });

    const authorizationUrl = buildAuthorizationUrl({ discovery, redirectUri, state, nonce, codeChallenge });

    return NextResponse.redirect(authorizationUrl);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown login startup error.";
    console.error("Failed to start Keycloak login.", error);
    return NextResponse.json(
      {
        error: "Failed to start Keycloak login.",
        detail: message,
      },
      { status: 500 },
    );
  }
}
