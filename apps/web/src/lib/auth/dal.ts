import "server-only";
import { cache } from "react";
import { redirect } from "next/navigation";
import { decryptSession, readSessionCookie, type SessionPayload } from "./session";
import { WebRole } from "./roles";

// Data Access Layer: the single place session validity is checked, per Next.js's
// recommended auth pattern. Real Keycloak verification (JWKS/issuer checks) will
// replace decryptSession's internals later without changing this file's callers.
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
