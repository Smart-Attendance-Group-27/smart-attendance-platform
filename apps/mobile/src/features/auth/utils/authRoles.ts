import type {
  AuthRole,
  AuthSession,
} from '../types/auth.types';

const authRoles: readonly AuthRole[] = [
  'student',
  'lecturer',
  'administrator',
];

export const studentMobileRole: AuthRole = 'student';

export function toAuthRoles(roles: readonly string[]): readonly AuthRole[] {
  const roleSet = new Set(roles);

  return authRoles.filter((role) => roleSet.has(role));
}

export function hasAuthRole(session: AuthSession, role: AuthRole) {
  return session.status === 'authenticated' && session.roles.includes(role);
}
