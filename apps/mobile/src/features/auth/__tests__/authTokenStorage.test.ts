import { describe, expect, test } from '@jest/globals';

import { areStoredAuthTokensFresh } from '../storage/authTokenStorage';
import type { StoredAuthTokens } from '../types/auth.types';

const now = 1_000_000;

function buildTokens(overrides: Partial<StoredAuthTokens> = {}): StoredAuthTokens {
  return {
    accessToken: 'access-token',
    issuedAt: now,
    ...overrides,
  };
}

describe('areStoredAuthTokensFresh', () => {
  test('treats a token with no expiry as stale', () => {
    // Keycloak omitted expires_in, so how long the token has left is unknown.
    // Assuming it never expires would strand the session on a dead token.
    expect(areStoredAuthTokensFresh(buildTokens(), now)).toBe(false);
  });

  test('treats an epoch expiry as stale rather than missing', () => {
    expect(areStoredAuthTokensFresh(buildTokens({ expiresAt: 0 }), now)).toBe(false);
  });

  test('is fresh while more than the refresh margin remains', () => {
    expect(
      areStoredAuthTokensFresh(buildTokens({ expiresAt: now + 61 }), now),
    ).toBe(true);
  });

  test('is stale once only the refresh margin remains', () => {
    // The margin is the point of the check: refresh before the token dies,
    // not after.
    expect(
      areStoredAuthTokensFresh(buildTokens({ expiresAt: now + 60 }), now),
    ).toBe(false);
  });

  test('is stale inside the refresh margin', () => {
    expect(
      areStoredAuthTokensFresh(buildTokens({ expiresAt: now + 30 }), now),
    ).toBe(false);
  });

  test('is stale once the token has already expired', () => {
    expect(
      areStoredAuthTokensFresh(buildTokens({ expiresAt: now - 1 }), now),
    ).toBe(false);
  });
});
