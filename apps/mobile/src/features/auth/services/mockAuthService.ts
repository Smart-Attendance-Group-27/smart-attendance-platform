import type {
  AuthService,
  AuthSignInResult,
} from './auth.service';
import type { AuthSession } from '../types/auth.types';

type MockAuthServiceOptions = {
  readonly initialSession?: AuthSession;
  readonly authenticatedUserId?: string;
  readonly simulateSignInFailure?: boolean;
};

const unauthenticatedSession: AuthSession = {
  status: 'unauthenticated',
};

const defaultAuthenticatedUserId = 'mock-student-user-1';

export class MockAuthService implements AuthService {
  private session: AuthSession;

  private readonly authenticatedUserId: string;

  private readonly simulateSignInFailure: boolean;

  constructor({
    initialSession = unauthenticatedSession,
    authenticatedUserId = defaultAuthenticatedUserId,
    simulateSignInFailure = false,
  }: MockAuthServiceOptions = {}) {
    this.session = initialSession;
    this.authenticatedUserId = authenticatedUserId;
    this.simulateSignInFailure = simulateSignInFailure;
  }

  async restoreSession(): Promise<AuthSession> {
    return this.session;
  }

  async signIn(): Promise<AuthSignInResult> {
    if (this.simulateSignInFailure) {
      return {
        success: false,
      };
    }

    this.session = {
      status: 'authenticated',
      userId: this.authenticatedUserId,
    };

    return {
      success: true,
      session: this.session,
    };
  }

  async signOut(): Promise<AuthSession> {
    this.session = unauthenticatedSession;

    return this.session;
  }
}
