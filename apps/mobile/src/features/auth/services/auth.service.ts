import type { AuthSession } from '../types/auth.types';

export type AuthSignInResult =
  | {
      readonly success: true;
      readonly session: AuthSession;
    }
  | {
      readonly success: false;
    };

export type AuthService = {
  restoreSession: () => Promise<AuthSession>;
  signIn: () => Promise<AuthSignInResult>;
  signOut: () => Promise<AuthSession>;
};
