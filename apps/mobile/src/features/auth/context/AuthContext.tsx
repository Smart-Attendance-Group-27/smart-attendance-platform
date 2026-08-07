import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
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

import { keycloakAuthConfig } from '../config/keycloakConfig';
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
import {
  hasAuthRole,
  studentMobileRole,
  toAuthRoles,
} from '../utils/authRoles';
import {
  getJwtRoles,
  getJwtSubject,
} from '../utils/jwt';

WebBrowser.maybeCompleteAuthSession();

type AuthContextValue = {
  readonly clearAuthError: () => void;
  readonly errorMessage: string | null;
  readonly isAuthRequestReady: boolean;
  readonly isRestoring: boolean;
  readonly isSigningIn: boolean;
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

const unauthorizedStudentMessage =
  'This account does not have student mobile access. Please sign in with a student account.';

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const redirectUri = makeRedirectUri({
  scheme: keycloakAuthConfig.redirectScheme,
  path: keycloakAuthConfig.redirectPath,
});

export function AuthProvider({ children }: PropsWithChildren) {
  const discovery = useAutoDiscovery(keycloakAuthConfig.issuerUrl);
  const [session, setSession] = useState<AuthSession>(unauthenticatedSession);
  const [isRestoring, setIsRestoring] = useState(true);
  const [isSigningIn, setIsSigningIn] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

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
          const restoredSession = createStudentSession(storedTokens);

          if (!restoredSession) {
            await clearStoredAuthTokens();
            if (!isMounted) {
              return;
            }
            setSession(unauthenticatedSession);
            setErrorMessage(unauthorizedStudentMessage);
            return;
          }

          setSession(restoredSession);
          return;
        }

        if (!storedTokens.refreshToken || !discovery?.tokenEndpoint) {
          await clearStoredAuthTokens();
          if (!isMounted) {
            return;
          }
          setSession(sessionExpired);
          setErrorMessage('Your session expired. Please sign in again.');
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
        const refreshedSession = createStudentSession(nextStoredTokens);

        if (!refreshedSession) {
          await clearStoredAuthTokens();
          if (!isMounted) {
            return;
          }
          setSession(unauthenticatedSession);
          setErrorMessage(unauthorizedStudentMessage);
          return;
        }

        await saveStoredAuthTokens(nextStoredTokens);
        if (!isMounted) {
          return;
        }
        setSession(refreshedSession);
      } catch {
        await clearStoredAuthTokens();
        if (!isMounted) {
          return;
        }
        setSession(sessionExpired);
        setErrorMessage('Your session expired. Please sign in again.');
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
      const nextSession = createStudentSession(storedTokens);

      if (!nextSession) {
        await clearStoredAuthTokens();
        setSession(unauthenticatedSession);
        setErrorMessage(unauthorizedStudentMessage);
        return;
      }

      await saveStoredAuthTokens(storedTokens);
      setSession(nextSession);
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

  const signOut = useCallback(async () => {
    setErrorMessage(null);
    await clearStoredAuthTokens();
    setSession(unauthenticatedSession);
  }, []);

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

function createStudentSession(tokens: StoredAuthTokens): AuthSession | null {
  const session = createAuthenticatedSession(tokens);

  return hasAuthRole(session, studentMobileRole) ? session : null;
}

function createAuthenticatedSession(tokens: StoredAuthTokens): AuthSession {
  return {
    status: 'authenticated',
    userId:
      getJwtSubject(tokens.idToken) ??
      getJwtSubject(tokens.accessToken) ??
      'keycloak-user',
    roles: toAuthRoles([
      ...getJwtRoles(tokens.accessToken, keycloakAuthConfig.clientId),
      ...getJwtRoles(tokens.idToken, keycloakAuthConfig.clientId),
    ]),
    accessToken: tokens.accessToken,
    expiresAt: tokens.expiresAt,
    idToken: tokens.idToken,
    refreshToken: tokens.refreshToken,
  };
}
