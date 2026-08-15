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

export type {
  FreshLocationReading,
  FreshLocationResult,
} from '../features/location/types/locationReading';
export type { LocationProvider } from '../features/location/services/locationProvider';
export { ExpoLocationProvider } from '../features/location/services/expoLocationProvider';
export { LiveLocationService } from '../features/location/services/liveLocationService';
export type {
  GeofenceAttempt,
  GeofenceAttemptResult,
  GeofenceDecision,
  GeofenceNextStep,
  GeofenceReason,
  SubmitGeofenceAttemptRequest,
} from '../features/location/types/geofenceAttempt';
export type { GeofenceValidationApiService } from '../features/location/services/geofenceValidationApiService';
export { CoreApiGeofenceValidationService } from '../features/location/services/coreApiGeofenceValidationService';
export type {
  ActiveAttendanceSession,
  ActiveAttendanceSessionsResult,
} from '../features/dashboard/types/activeAttendanceSession';
export type { ActiveAttendanceSessionService } from '../features/dashboard/services/activeAttendanceSessionService';
export { CoreApiActiveAttendanceSessionService } from '../features/dashboard/services/coreApiActiveAttendanceSessionService';
