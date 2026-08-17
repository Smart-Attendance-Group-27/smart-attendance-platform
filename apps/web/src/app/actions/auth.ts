"use server";

import { redirect } from "next/navigation";
import { deleteSession } from "@/lib/auth/session";
import { verifySession, getFreshIdTokenForLogout } from "@/lib/auth/dal";
import { buildEndSessionUrl, getOidcDiscovery, isKeycloakConfigured } from "@/lib/auth/oidc";

export async function signOut(): Promise<void> {
  const session = await verifySession();

  let redirectTarget = "/login";

  if (session && isKeycloakConfigured()) {
    const idToken = await getFreshIdTokenForLogout(session);
    if (idToken) {
      try {
        const discovery = await getOidcDiscovery();
        const webBaseUrl = process.env.WEB_BASE_URL ?? "http://localhost:3000";
        redirectTarget = buildEndSessionUrl({
          discovery,
          idTokenHint: idToken,
          postLogoutRedirectUri: `${webBaseUrl}/login`,
        });
      } catch {
        // Keycloak discovery unreachable — the local session is cleared below
        // regardless, so falling back to a plain redirect still signs out locally.
      }
    }
  }

  await deleteSession();
  redirect(redirectTarget);
}
