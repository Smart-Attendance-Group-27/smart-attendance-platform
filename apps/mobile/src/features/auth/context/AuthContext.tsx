import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  exchangeCodeAsync,
  makeRedirectUri,
  refreshAsync,
  ResponseType,
  type TokenResponse,
  useAuthRequest,
  useAutoDiscovery,
} from 'expo-auth-session';
import * as WebBrowser from 'expo-web-browser';

import {
  buildKeycloakLogoutUrl,
  keycloakAuthConfig,
} from '../config/keycloakConfig';
import {
  areStoredAuthTokensFresh,
  clearStoredAuthTokens,
  loadStoredAuthTokens,
  saveStoredAuthTokens,
} from '../storage/authTokenStorage';
import type {
  AuthSession,
  StoredAuthTokens,
} from '../types/auth.types';
import { getJwtSubject } from '../utils/jwt';
import { setDefaultAccessTokenRefresher } from '../../../services/api/coreApiClient';

WebBrowser.maybeCompleteAuthSession();

const sessionExpiredMessage = 'Your session expired. Please sign in again.';

type AuthContextValue = {
  readonly clearAuthError: () => void;
  readonly errorMessage: string | null;
  readonly isAuthRequestReady: boolean;
  readonly isRestoring: boolean;
  readonly isSigningIn: boolean;
  readonly refreshAccessToken: () => Promise<string | undefined>;
  readonly session: AuthSession;
  readonly signIn: () => Promise<void>;
  readonly signOut: () => Promise<void>;
};

const unauthenticatedSession: AuthSession = {
  status: 'unauthenticated',
};

const sessionExpired: AuthSession = {
  status: 'session-expired',
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const redirectUri = makeRedirectUri({
  scheme: keycloakAuthConfig.redirectScheme,
  path: keycloakAuthConfig.redirectPath,
});

const logoutRedirectUri = makeRedirectUri({
  scheme: keycloakAuthConfig.redirectScheme,
  path: keycloakAuthConfig.logoutRedirectPath,
});

export function AuthProvider({ children }: PropsWithChildren) {
  const discovery = useAutoDiscovery(keycloakAuthConfig.issuerUrl);
  const [session, setSession] = useState<AuthSession>(unauthenticatedSession);
  const [isRestoring, setIsRestoring] = useState(true);
  const [isSigningIn, setIsSigningIn] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const refreshInFlight = useRef<Promise<string | undefined> | null>(null);

  const [request, , promptAsync] = useAuthRequest(
    {
      clientId: keycloakAuthConfig.clientId,
      redirectUri,
      responseType: ResponseType.Code,
      scopes: [...keycloakAuthConfig.scopes],
      usePKCE: true,
    },
    discovery,
  );

  useEffect(() => {
    let isMounted = true;

    const restoreSession = async () => {
      try {
        const storedTokens = await loadStoredAuthTokens();

        if (!isMounted) {
          return;
        }

        if (!storedTokens) {
          setSession(unauthenticatedSession);
          return;
        }

        if (areStoredAuthTokensFresh(storedTokens)) {
          setSession(createAuthenticatedSession(storedTokens));
          return;
        }

        if (!storedTokens.refreshToken || !discovery?.tokenEndpoint) {
          await clearStoredAuthTokens();
          if (!isMounted) {
            return;
          }
          setSession(sessionExpired);
          setErrorMessage(sessionExpiredMessage);
          return;
        }

        const refreshedTokens = await refreshAsync(
          {
            clientId: keycloakAuthConfig.clientId,
            refreshToken: storedTokens.refreshToken,
            scopes: [...keycloakAuthConfig.scopes],
          },
          discovery,
        );
        const nextStoredTokens = buildStoredAuthTokens(refreshedTokens);

        await saveStoredAuthTokens(nextStoredTokens);
        if (!isMounted) {
          return;
        }
        setSession(createAuthenticatedSession(nextStoredTokens));
      } catch {
        await clearStoredAuthTokens();
        if (!isMounted) {
          return;
        }
        setSession(sessionExpired);
        setErrorMessage(sessionExpiredMessage);
      } finally {
        if (isMounted) {
          setIsRestoring(false);
        }
      }
    };

    void restoreSession();

    return () => {
      isMounted = false;
    };
  }, [discovery]);

  const signIn = useCallback(async () => {
    setErrorMessage(null);

    if (!discovery || !request) {
      setErrorMessage(
        'Keycloak is not ready yet. Check that Docker is running and try again.',
      );
      return;
    }

    setIsSigningIn(true);

    try {
      const result = await promptAsync();

      if (result.type === 'cancel' || result.type === 'dismiss') {
        setErrorMessage('Login was cancelled.');
        return;
      }

      if (result.type !== 'success') {
        setErrorMessage('Login failed. Please try again.');
        return;
      }

      const code = result.params.code;

      if (!code || !request.codeVerifier) {
        setErrorMessage('Login response was incomplete. Please try again.');
        return;
      }

      const tokenResponse = await exchangeCodeAsync(
        {
          clientId: keycloakAuthConfig.clientId,
          code,
          extraParams: {
            code_verifier: request.codeVerifier,
          },
          redirectUri,
          scopes: [...keycloakAuthConfig.scopes],
        },
        discovery,
      );
      const storedTokens = buildStoredAuthTokens(tokenResponse);

      await saveStoredAuthTokens(storedTokens);
      setSession(createAuthenticatedSession(storedTokens));
    } catch {
      setErrorMessage(
        'Could not complete Keycloak login. Check local Keycloak and try again.',
      );
    } finally {
      setIsSigningIn(false);
    }
  }, [
    discovery,
    promptAsync,
    request,
  ]);

  /**
   * Renews the session and returns a usable access token, or `undefined` when
   * the user has to sign in again.
   *
   * Concurrent callers share one round trip. Several screens can be in flight
   * at once - the dashboard alone builds five clients - and letting each one
   * present the same refresh token independently would have Keycloak race
   * itself, with whichever response landed last deciding the stored session.
   */
  const refreshAccessToken = useCallback(async (): Promise<string | undefined> => {
    if (refreshInFlight.current) {
      return refreshInFlight.current;
    }

    const endSession = async () => {
      await clearStoredAuthTokens();
      setSession(sessionExpired);
      setErrorMessage(sessionExpiredMessage);
      return undefined;
    };

    const run = async (): Promise<string | undefined> => {
      const storedTokens = await loadStoredAuthTokens();

      if (!storedTokens?.refreshToken || !discovery?.tokenEndpoint) {
        return endSession();
      }

      try {
        const refreshedTokens = await refreshAsync(
          {
            clientId: keycloakAuthConfig.clientId,
            refreshToken: storedTokens.refreshToken,
            scopes: [...keycloakAuthConfig.scopes],
          },
          discovery,
        );
        const nextStoredTokens = buildStoredAuthTokens(refreshedTokens);

        await saveStoredAuthTokens(nextStoredTokens);
        setSession(createAuthenticatedSession(nextStoredTokens));
        return nextStoredTokens.accessToken;
      } catch {
        // The refresh token is expired or was revoked at Keycloak.
        return endSession();
      }
    };

    const pending = run().finally(() => {
      refreshInFlight.current = null;
    });
    refreshInFlight.current = pending;

    return pending;
  }, [discovery]);

  // One registration for every CoreApiClient in the app, including the ones
  // screens build for themselves.
  useEffect(() => {
    setDefaultAccessTokenRefresher(refreshAccessToken);

    return () => {
      setDefaultAccessTokenRefresher(undefined);
    };
  }, [refreshAccessToken]);

  const signOut = useCallback(async () => {
    const idToken = session.status === 'authenticated' ? session.idToken : undefined;
    const logoutUrl = buildKeycloakLogoutUrl({
      idToken,
      postLogoutRedirectUri: logoutRedirectUri,
    });

    setErrorMessage(null);
    await clearStoredAuthTokens();
    setSession(unauthenticatedSession);

    try {
      await WebBrowser.openAuthSessionAsync(logoutUrl, logoutRedirectUri);
    } catch {
      setErrorMessage('Signed out locally, but Keycloak logout could not be opened.');
    }
  }, [session]);

  const clearAuthError = useCallback(() => {
    setErrorMessage(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      clearAuthError,
      errorMessage,
      isAuthRequestReady: Boolean(discovery && request),
      isRestoring,
      isSigningIn,
      refreshAccessToken,
      session,
      signIn,
      signOut,
    }),
    [
      clearAuthError,
      discovery,
      errorMessage,
      isRestoring,
      isSigningIn,
      refreshAccessToken,
      request,
      session,
      signIn,
      signOut,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const auth = useContext(AuthContext);

  if (!auth) {
    throw new Error('useAuth must be used inside AuthProvider');
  }

  return auth;
}

function buildStoredAuthTokens(tokenResponse: TokenResponse): StoredAuthTokens {
  return {
    accessToken: tokenResponse.accessToken,
    expiresAt:
      tokenResponse.expiresIn === undefined
        ? undefined
        : tokenResponse.issuedAt + tokenResponse.expiresIn,
    expiresIn: tokenResponse.expiresIn,
    idToken: tokenResponse.idToken,
    issuedAt: tokenResponse.issuedAt,
    refreshToken: tokenResponse.refreshToken,
    tokenType: tokenResponse.tokenType,
  };
}

function createAuthenticatedSession(tokens: StoredAuthTokens): AuthSession {
  return {
    status: 'authenticated',
    userId:
      getJwtSubject(tokens.idToken) ??
      getJwtSubject(tokens.accessToken) ??
      'keycloak-user',
    accessToken: tokens.accessToken,
    expiresAt: tokens.expiresAt,
    idToken: tokens.idToken,
    refreshToken: tokens.refreshToken,
  };
}
