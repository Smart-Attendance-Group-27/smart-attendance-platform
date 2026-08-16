import type { CoreApiFailureStatus } from '../../../services/api/coreApiClient';
import type { FreshLocationReading } from './locationReading';

export type GeofenceDecision = 'PASSED' | 'FAILED' | 'RETRY_REQUIRED';
export type GeofenceNextStep =
  | 'FACE_VERIFICATION'
  | 'RETRY_LOCATION'
  | 'NONE';

export type GeofenceReason =
  | 'MOCK_LOCATION_DETECTED'
  | 'ACCURACY_UNAVAILABLE'
  | 'LOCATION_ACCURACY_TOO_LOW'
  | 'STALE_LOCATION'
  | 'CAPTURE_TIME_IN_FUTURE'
  | 'OUTSIDE_GEOFENCE'
  | 'NEAR_GEOFENCE_BOUNDARY'
  | 'SESSION_NOT_ACTIVE'
  | 'CHECK_IN_NOT_OPEN'
  | 'CHECK_IN_CLOSED'
  | 'STUDENT_NOT_ELIGIBLE'
  | 'GEOFENCE_NOT_CONFIGURED'
  | 'ATTEMPT_LIMIT_REACHED';

export type GeofenceAttempt = {
  readonly verificationAttemptId: string;
  readonly attemptNumber: number;
  readonly decision: GeofenceDecision;
  readonly distanceM: number;
  readonly allowedRadiusM: number;
  readonly nextStep: GeofenceNextStep;
  readonly reason: GeofenceReason | null;
};

export type GeofenceAttemptResult =
  | { readonly status: 'completed'; readonly attempt: GeofenceAttempt }
  | { readonly status: CoreApiFailureStatus };

export type SubmitGeofenceAttemptRequest = {
  readonly sessionId: string;
  readonly reading: FreshLocationReading;
};
