import type {
  GeofenceAttemptResult,
  SubmitGeofenceAttemptRequest,
} from '../types/geofenceAttempt';

export interface GeofenceValidationApiService {
  submitAttempt(
    request: SubmitGeofenceAttemptRequest,
  ): Promise<GeofenceAttemptResult>;
}
