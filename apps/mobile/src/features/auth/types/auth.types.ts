export type AuthSessionStatus =
  | 'authenticated'
  | 'session-expired'
  | 'unauthenticated';

export type AuthRole =
  | 'administrator'
  | 'lecturer'
  | 'student';

export type AuthenticatedSession = {
  readonly status: 'authenticated';
  readonly userId: string;
  readonly roles: readonly AuthRole[];
  readonly accessToken?: string;
  readonly refreshToken?: string;
  readonly idToken?: string;
  readonly expiresAt?: number;
};

export type UnauthenticatedSession = {
  readonly status: 'unauthenticated';
};

export type SessionExpiredSession = {
  readonly status: 'session-expired';
};

export type AuthSession =
  | AuthenticatedSession
  | SessionExpiredSession
  | UnauthenticatedSession;

export type StoredAuthTokens = {
  readonly accessToken: string;
  readonly expiresAt?: number;
  readonly expiresIn?: number;
  readonly idToken?: string;
  readonly issuedAt: number;
  readonly refreshToken?: string;
  readonly tokenType?: string;
};
