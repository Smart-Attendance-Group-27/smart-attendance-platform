// Mirrors the Keycloak realm roles in infra/local/keycloak/realm/uniattend-realm.json.
// The "student" role exists in that realm too but has no web surface — mobile only.
export const LECTURER_ROLE = "lecturer";
export const ADMINISTRATOR_ROLE = "administrator";

export type WebRole = typeof LECTURER_ROLE | typeof ADMINISTRATOR_ROLE;

export function isWebRole(value: string): value is WebRole {
  return value === LECTURER_ROLE || value === ADMINISTRATOR_ROLE;
}

export function dashboardPathForRole(role: WebRole): string {
  return role === ADMINISTRATOR_ROLE ? "/admin/dashboard" : "/lecturer/dashboard";
}
