export function getJwtSubject(token?: string) {
  const payload = decodeJwtPayload(token);
  const subject = payload?.sub;

  return typeof subject === 'string' ? subject : null;
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
