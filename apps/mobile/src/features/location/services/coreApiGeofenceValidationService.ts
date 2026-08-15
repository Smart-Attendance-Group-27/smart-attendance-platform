import type { CoreApiClient } from '../../../services/api/coreApiClient';
import type {
  GeofenceAttempt,
  GeofenceAttemptResult,
  GeofenceDecision,
  GeofenceNextStep,
  GeofenceReason,
  SubmitGeofenceAttemptRequest,
} from '../types/geofenceAttempt';
import type { GeofenceValidationApiService } from './geofenceValidationApiService';

type GeofenceAttemptResponse = {
  readonly verificationAttemptId?: unknown;
  readonly attemptNumber?: unknown;
  readonly decision?: unknown;
  readonly distanceM?: unknown;
  readonly allowedRadiusM?: unknown;
  readonly nextStep?: unknown;
  readonly reason?: unknown;
};

const decisions = new Set<GeofenceDecision>([
  'PASSED',
  'FAILED',
  'RETRY_REQUIRED',
]);
const nextSteps = new Set<GeofenceNextStep>([
  'FACE_VERIFICATION',
  'RETRY_LOCATION',
  'NONE',
]);
const reasons = new Set<GeofenceReason>([
  'MOCK_LOCATION_DETECTED',
  'ACCURACY_UNAVAILABLE',
  'LOCATION_ACCURACY_TOO_LOW',
  'STALE_LOCATION',
  'CAPTURE_TIME_IN_FUTURE',
  'OUTSIDE_GEOFENCE',
  'NEAR_GEOFENCE_BOUNDARY',
  'SESSION_NOT_ACTIVE',
  'CHECK_IN_NOT_OPEN',
  'CHECK_IN_CLOSED',
  'STUDENT_NOT_ELIGIBLE',
  'GEOFENCE_NOT_CONFIGURED',
  'ATTEMPT_LIMIT_REACHED',
]);

export class CoreApiGeofenceValidationService
  implements GeofenceValidationApiService
{
  constructor(private readonly coreApiClient: CoreApiClient) {}

  async submitAttempt({
    sessionId,
    reading,
  }: SubmitGeofenceAttemptRequest): Promise<GeofenceAttemptResult> {
    const path = `/api/v1/attendance-sessions/${encodeURIComponent(
      sessionId,
    )}/geofence-attempts`;
    const result = await this.coreApiClient.post<GeofenceAttemptResponse>(
      path,
      {
        latitude: reading.latitude,
        longitude: reading.longitude,
        accuracyM: reading.accuracyM,
        capturedAt: reading.capturedAt,
        mocked: reading.mocked,
      },
    );

    if (result.status !== 'ok') {
      return { status: result.status };
    }

    const attempt = toGeofenceAttempt(result.data);
    return attempt
      ? { status: 'completed', attempt }
      : { status: 'server-error' };
  }
}

function toGeofenceAttempt(
  response: GeofenceAttemptResponse,
): GeofenceAttempt | null {
  if (
    typeof response.verificationAttemptId !== 'string' ||
    !Number.isInteger(response.attemptNumber) ||
    (response.attemptNumber as number) < 1 ||
    typeof response.decision !== 'string' ||
    !decisions.has(response.decision as GeofenceDecision) ||
    !isNonnegativeFiniteNumber(response.distanceM) ||
    !isPositiveFiniteNumber(response.allowedRadiusM) ||
    typeof response.nextStep !== 'string' ||
    !nextSteps.has(response.nextStep as GeofenceNextStep) ||
    !isReason(response.reason) ||
    !isCoherentOutcome(
      response.decision as GeofenceDecision,
      response.nextStep as GeofenceNextStep,
      response.reason,
    )
  ) {
    return null;
  }

  return {
    verificationAttemptId: response.verificationAttemptId,
    attemptNumber: response.attemptNumber as number,
    decision: response.decision as GeofenceDecision,
    distanceM: response.distanceM,
    allowedRadiusM: response.allowedRadiusM,
    nextStep: response.nextStep as GeofenceNextStep,
    reason: response.reason,
  };
}

function isCoherentOutcome(
  decision: GeofenceDecision,
  nextStep: GeofenceNextStep,
  reason: GeofenceReason | null,
): boolean {
  if (decision === 'PASSED') {
    return nextStep === 'FACE_VERIFICATION' && reason === null;
  }

  if (decision === 'RETRY_REQUIRED') {
    return nextStep === 'RETRY_LOCATION' && reason !== null;
  }

  return nextStep === 'NONE' && reason !== null;
}

function isReason(value: unknown): value is GeofenceReason | null {
  return (
    value === null ||
    (typeof value === 'string' && reasons.has(value as GeofenceReason))
  );
}

function isNonnegativeFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0;
}

function isPositiveFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value > 0;
}
