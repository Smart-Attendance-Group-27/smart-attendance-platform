"use server";

import { redirect } from "next/navigation";
import { createSession, deleteSession } from "@/lib/auth/session";
import { dashboardPathForRole, isWebRole } from "@/lib/auth/roles";

// MOCK sign-in: no credential/OIDC verification. Keycloak (uniattend-web client,
// Authorization Code + PKCE, mirroring apps/mobile's flow) replaces this action's
// body once the client is provisioned in infra/local/keycloak/realm — everything
// downstream (session cookie, DAL, role guards) stays the same.
export async function mockSignIn(formData: FormData): Promise<void> {
  const role = formData.get("role");
  const name = formData.get("name");

  if (typeof role !== "string" || !isWebRole(role) || typeof name !== "string" || !name.trim()) {
    throw new Error("Invalid mock sign-in payload.");
  }

  await createSession(`mock-${role}`, name.trim(), role);
  redirect(dashboardPathForRole(role));
}

export async function signOut(): Promise<void> {
  await deleteSession();
  redirect("/login");
}
