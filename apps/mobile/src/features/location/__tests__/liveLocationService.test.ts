import { describe, expect, jest, test } from '@jest/globals';

import type { GeofenceAttemptResult } from '../types/geofenceAttempt';
import type { FreshLocationResult } from '../types/locationReading';
import { LiveLocationService } from '../services/liveLocationService';
import type { GeofenceValidationApiService } from '../services/geofenceValidationApiService';
import type { LocationProvider } from '../services/locationProvider';

const reading = {
  latitude: 6.795132,
  longitude: 79.900421,
  accuracyM: 18.5,
  capturedAt: '2026-08-13T05:30:14.000Z',
  mocked: false,
};

function buildService(
  locationResult: FreshLocationResult,
  attemptResult: GeofenceAttemptResult = {
    status: 'completed',
    attempt: {
      verificationAttemptId: '50000000-0000-0000-0000-000000000001',
      attemptNumber: 1,
      decision: 'PASSED',
      distanceM: 18.7,
      allowedRadiusM: 70,
      nextStep: 'FACE_VERIFICATION',
      reason: null,
    },
  },
) {
  const captureFreshLocation =
    jest.fn<LocationProvider['captureFreshLocation']>();
  captureFreshLocation.mockResolvedValue(locationResult);
  const submitAttempt =
    jest.fn<GeofenceValidationApiService['submitAttempt']>();
  submitAttempt.mockResolvedValue(attemptResult);

  return {
    service: new LiveLocationService(
      { captureFreshLocation },
      { submitAttempt },
    ),
    captureFreshLocation,
    submitAttempt,
  };
}

function completedAttempt(
  decision: 'FAILED' | 'RETRY_REQUIRED',
  reason:
    | 'OUTSIDE_GEOFENCE'
    | 'MOCK_LOCATION_DETECTED'
    | 'ACCURACY_UNAVAILABLE'
    | 'LOCATION_ACCURACY_TOO_LOW'
    | 'STALE_LOCATION'
    | 'CAPTURE_TIME_IN_FUTURE'
    | 'NEAR_GEOFENCE_BOUNDARY'
    | 'STUDENT_NOT_ELIGIBLE'
    | 'ATTEMPT_LIMIT_REACHED'
    | 'SESSION_NOT_ACTIVE'
    | 'CHECK_IN_NOT_OPEN'
    | 'CHECK_IN_CLOSED'
    | 'GEOFENCE_NOT_CONFIGURED',
): GeofenceAttemptResult {
  return {
    status: 'completed',
    attempt: {
      verificationAttemptId: '50000000-0000-0000-0000-000000000001',
      attemptNumber: 1,
      decision,
      distanceM: 74,
      allowedRadiusM: 70,
      nextStep: decision === 'FAILED' ? 'NONE' : 'RETRY_LOCATION',
      reason,
    },
  };
}

describe('LiveLocationService', () => {
  test('submits the fresh phone reading for the requested session', async () => {
    const { service, submitAttempt } = buildService({
      status: 'captured',
      reading,
    });

    await expect(
      service.validateLocation('attendance-session-active'),
    ).resolves.toEqual({ status: 'inside_geofence' });
    expect(submitAttempt).toHaveBeenCalledWith({
      sessionId: 'attendance-session-active',
      reading,
    });
  });

  test.each([
    {
      providerStatus: 'permission_denied',
      expectedStatus: 'permission_denied',
    },
    {
      providerStatus: 'services_disabled',
      expectedStatus: 'services_disabled',
    },
    { providerStatus: 'unavailable', expectedStatus: 'unavailable' },
  ] as const)(
    'maps provider status $providerStatus without calling the API',
    async ({ providerStatus, expectedStatus }) => {
      const { service, submitAttempt } = buildService({
        status: providerStatus,
      });

      await expect(
        service.validateLocation('attendance-session-active'),
      ).resolves.toEqual({ status: expectedStatus });
      expect(submitAttempt).not.toHaveBeenCalled();
    },
  );

  test.each([
    {
      reason: 'OUTSIDE_GEOFENCE',
      decision: 'FAILED',
      expectedStatus: 'outside_geofence',
    },
    {
      reason: 'MOCK_LOCATION_DETECTED',
      decision: 'FAILED',
      expectedStatus: 'mock_location_detected',
    },
    {
      reason: 'ACCURACY_UNAVAILABLE',
      decision: 'RETRY_REQUIRED',
      expectedStatus: 'poor_accuracy',
    },
    {
      reason: 'LOCATION_ACCURACY_TOO_LOW',
      decision: 'RETRY_REQUIRED',
      expectedStatus: 'poor_accuracy',
    },
    {
      reason: 'STALE_LOCATION',
      decision: 'RETRY_REQUIRED',
      expectedStatus: 'stale_location',
    },
    {
      reason: 'CAPTURE_TIME_IN_FUTURE',
      decision: 'RETRY_REQUIRED',
      expectedStatus: 'stale_location',
    },
    {
      reason: 'NEAR_GEOFENCE_BOUNDARY',
      decision: 'RETRY_REQUIRED',
      expectedStatus: 'retry_required',
    },
    {
      reason: 'STUDENT_NOT_ELIGIBLE',
      decision: 'FAILED',
      expectedStatus: 'forbidden',
    },
    {
      reason: 'ATTEMPT_LIMIT_REACHED',
      decision: 'FAILED',
      expectedStatus: 'attempt_limit_reached',
    },
    {
      reason: 'SESSION_NOT_ACTIVE',
      decision: 'FAILED',
      expectedStatus: 'session_unavailable',
    },
    {
      reason: 'CHECK_IN_NOT_OPEN',
      decision: 'FAILED',
      expectedStatus: 'session_unavailable',
    },
    {
      reason: 'CHECK_IN_CLOSED',
      decision: 'FAILED',
      expectedStatus: 'session_unavailable',
    },
    {
      reason: 'GEOFENCE_NOT_CONFIGURED',
      decision: 'FAILED',
      expectedStatus: 'session_unavailable',
    },
  ] as const)(
    'maps backend reason $reason to $expectedStatus',
    async ({ reason, decision, expectedStatus }) => {
      const { service } = buildService(
        { status: 'captured', reading },
        completedAttempt(decision, reason),
      );

      await expect(
        service.validateLocation('attendance-session-active'),
      ).resolves.toEqual({ status: expectedStatus });
    },
  );

  test.each([
    { apiStatus: 'unauthenticated', expectedStatus: 'unauthenticated' },
    { apiStatus: 'forbidden', expectedStatus: 'forbidden' },
    { apiStatus: 'not-found', expectedStatus: 'session_unavailable' },
    { apiStatus: 'invalid-request', expectedStatus: 'invalid_request' },
    { apiStatus: 'conflict', expectedStatus: 'session_unavailable' },
    { apiStatus: 'network-error', expectedStatus: 'network_error' },
    { apiStatus: 'server-error', expectedStatus: 'server_error' },
  ] as const)(
    'maps API failure $apiStatus without a mock fallback',
    async ({ apiStatus, expectedStatus }) => {
      const { service } = buildService(
        { status: 'captured', reading },
        { status: apiStatus },
      );

      await expect(
        service.validateLocation('attendance-session-active'),
      ).resolves.toEqual({ status: expectedStatus });
    },
  );
});
