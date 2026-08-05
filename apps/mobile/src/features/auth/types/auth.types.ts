export type AuthSessionStatus = 'authenticated' | 'unauthenticated';

export type AuthenticatedSession = {
  readonly status: 'authenticated';
  readonly userId: string;
};

export type UnauthenticatedSession = {
  readonly status: 'unauthenticated';
};

export type AuthSession = AuthenticatedSession | UnauthenticatedSession;
