import type { CoreApiFailureStatus } from '../../../services/api/coreApiClient';
import type {
  GeofenceAttempt,
  GeofenceReason,
} from '../types/geofenceAttempt';
import type { LocationValidationResult } from '../types/locationValidation';
import type { GeofenceValidationApiService } from './geofenceValidationApiService';
import type { LocationProvider } from './locationProvider';
import type { LocationService } from './locationService';

const apiFailureStates: Record<
  CoreApiFailureStatus,
  LocationValidationResult['status']
> = {
  unauthenticated: 'unauthenticated',
  forbidden: 'forbidden',
  'not-found': 'session_unavailable',
  'invalid-request': 'invalid_request',
  conflict: 'session_unavailable',
  'server-error': 'server_error',
  'network-error': 'network_error',
};

export class LiveLocationService implements LocationService {
  constructor(
    private readonly locationProvider: LocationProvider,
    private readonly geofenceApi: GeofenceValidationApiService,
  ) {}

  async validateLocation(
    sessionId: string,
  ): Promise<LocationValidationResult> {
    const locationResult = await this.locationProvider.captureFreshLocation();

    if (locationResult.status !== 'captured') {
      return {
        status:
          locationResult.status === 'permission_denied'
            ? 'permission_denied'
            : locationResult.status === 'services_disabled'
              ? 'services_disabled'
              : 'unavailable',
      };
    }

    const attemptResult = await this.geofenceApi.submitAttempt({
      sessionId,
      reading: locationResult.reading,
    });

    if (attemptResult.status !== 'completed') {
      return { status: apiFailureStates[attemptResult.status] };
    }

    return mapAttempt(attemptResult.attempt);
  }
}

function mapAttempt(attempt: GeofenceAttempt): LocationValidationResult {
  if (attempt.decision === 'PASSED') {
    return { status: 'inside_geofence' };
  }

  const reasonStatus = mapReason(attempt.reason);
  return reasonStatus
    ? { status: reasonStatus }
    : { status: 'server_error' };
}

function mapReason(
  reason: GeofenceReason | null,
): LocationValidationResult['status'] | null {
  switch (reason) {
    case 'OUTSIDE_GEOFENCE':
      return 'outside_geofence';
    case 'MOCK_LOCATION_DETECTED':
      return 'mock_location_detected';
    case 'ACCURACY_UNAVAILABLE':
    case 'LOCATION_ACCURACY_TOO_LOW':
      return 'poor_accuracy';
    case 'STALE_LOCATION':
    case 'CAPTURE_TIME_IN_FUTURE':
      return 'stale_location';
    case 'NEAR_GEOFENCE_BOUNDARY':
      return 'retry_required';
    case 'STUDENT_NOT_ELIGIBLE':
      return 'forbidden';
    case 'ATTEMPT_LIMIT_REACHED':
      return 'attempt_limit_reached';
    case 'SESSION_NOT_ACTIVE':
    case 'CHECK_IN_NOT_OPEN':
    case 'CHECK_IN_CLOSED':
    case 'GEOFENCE_NOT_CONFIGURED':
      return 'session_unavailable';
    default:
      return null;
  }
}
