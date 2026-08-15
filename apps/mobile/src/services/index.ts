export type {
  AuthenticatedSession,
  AuthSession,
  AuthSessionStatus,
  UnauthenticatedSession,
} from '../features/auth/types/auth.types';
export type {
  AuthService,
  AuthSignInResult,
} from '../features/auth/services/auth.service';
export { MockAuthService } from '../features/auth/services/mockAuthService';

export type {
  AccessTokenProvider,
  CoreApiClientOptions,
  CoreApiFailureStatus,
  CoreApiResult,
} from './api/coreApiClient';
export { CoreApiClient, resolveCoreApiBaseUrl } from './api/coreApiClient';

export type { StudentProfile } from '../features/profile/types/profile.types';
export type {
  ProfileService,
  StudentProfileResult,
} from '../features/profile/services/profile.service';
export { MockProfileService } from '../features/profile/services/mockProfileService';
export { CoreApiProfileService } from '../features/profile/services/coreApiProfileService';
