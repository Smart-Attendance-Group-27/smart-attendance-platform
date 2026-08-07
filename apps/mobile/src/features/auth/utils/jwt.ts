export function getJwtSubject(token?: string) {
  const payload = decodeJwtPayload(token);
  const subject = payload?.sub;

  return typeof subject === 'string' ? subject : null;
}

export function getJwtRoles(token?: string, clientId?: string) {
  const payload = decodeJwtPayload(token);

  if (!payload) {
    return [];
  }

  const roles = [
    ...getRealmRoles(payload),
    ...getClientRoles(payload, clientId),
  ];

  return [...new Set(roles)];
}

function decodeJwtPayload(token?: string): Record<string, unknown> | null {
  if (!token) {
    return null;
  }

  const [, payload] = token.split('.');

  if (!payload) {
    return null;
  }

  try {
    return JSON.parse(decodeBase64Url(payload)) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function getRealmRoles(payload: Record<string, unknown>) {
  const realmAccess = payload.realm_access;

  if (!isRecord(realmAccess)) {
    return [];
  }

  return getRoleValues(realmAccess.roles);
}

function getClientRoles(payload: Record<string, unknown>, clientId?: string) {
  if (!clientId) {
    return [];
  }

  const resourceAccess = payload.resource_access;

  if (!isRecord(resourceAccess)) {
    return [];
  }

  const clientAccess = resourceAccess[clientId];

  if (!isRecord(clientAccess)) {
    return [];
  }

  return getRoleValues(clientAccess.roles);
}

function getRoleValues(value: unknown) {
  return Array.isArray(value)
    ? value.filter((role): role is string => typeof role === 'string')
    : [];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function decodeBase64Url(value: string) {
  const normalized = value.replace(/-/g, '+').replace(/_/g, '/');
  const padded = normalized.padEnd(
    normalized.length + ((4 - (normalized.length % 4)) % 4),
    '=',
  );

  return decodeURIComponent(
    atob(padded)
      .split('')
      .map((character) =>
        `%${character.charCodeAt(0).toString(16).padStart(2, '0')}`,
      )
      .join(''),
  );
}
