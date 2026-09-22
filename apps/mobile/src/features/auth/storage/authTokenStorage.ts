import * as SecureStore from 'expo-secure-store';

import type { StoredAuthTokens } from '../types/auth.types';

const authTokensStorageKey = 'uniattend.auth.tokens';
const tokenRefreshMarginSeconds = 60;

const secureStoreOptions: SecureStore.SecureStoreOptions = {
  keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
};

export async function saveStoredAuthTokens(tokens: StoredAuthTokens) {
  await SecureStore.setItemAsync(
    authTokensStorageKey,
    JSON.stringify(tokens),
    secureStoreOptions,
  );
}

export async function loadStoredAuthTokens() {
  const rawTokens = await SecureStore.getItemAsync(
    authTokensStorageKey,
    secureStoreOptions,
  );

  if (!rawTokens) {
    return null;
  }

  try {
    const parsedTokens = JSON.parse(rawTokens) as unknown;

    if (isStoredAuthTokens(parsedTokens)) {
      return parsedTokens;
    }
  } catch {
    // Corrupt storage should behave like a signed-out session.
  }

  await clearStoredAuthTokens();
  return null;
}

export async function clearStoredAuthTokens() {
  await SecureStore.deleteItemAsync(authTokensStorageKey, secureStoreOptions);
}

/**
 * Whether the stored access token can still be used as-is.
 *
 * Tokens without a known expiry are treated as stale, not fresh. Keycloak omits
 * `expires_in` only rarely, but when it does we cannot tell how long the token
 * has left — and assuming "forever" strands the session on a token the API has
 * already started rejecting. Reporting it stale sends the caller down the
 * refresh path instead, which either renews the session or ends it honestly.
 */
export function areStoredAuthTokensFresh(
  tokens: StoredAuthTokens,
  nowSeconds = Date.now() / 1000,
) {
  if (tokens.expiresAt === undefined) {
    return false;
  }

  return tokens.expiresAt - nowSeconds > tokenRefreshMarginSeconds;
}

function isStoredAuthTokens(value: unknown): value is StoredAuthTokens {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.accessToken === 'string' &&
    typeof value.issuedAt === 'number' &&
    isOptionalNumber(value.expiresAt) &&
    isOptionalNumber(value.expiresIn) &&
    isOptionalString(value.idToken) &&
    isOptionalString(value.refreshToken) &&
    isOptionalString(value.tokenType)
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isOptionalNumber(value: unknown) {
  return value === undefined || typeof value === 'number';
}

function isOptionalString(value: unknown) {
  return value === undefined || typeof value === 'string';
}
