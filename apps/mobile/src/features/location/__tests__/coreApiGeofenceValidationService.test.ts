import {
  afterEach,
  beforeEach,
  describe,
  expect,
  jest,
  test,
} from '@jest/globals';

import { CoreApiClient } from '../../../services/api/coreApiClient';
import { CoreApiGeofenceValidationService } from '../services/coreApiGeofenceValidationService';
import type { FreshLocationReading } from '../types/locationReading';

const accessToken = 'header.payload.signature';
const sessionId = '40000000-0000-0000-0000-000000000001';
const reading: FreshLocationReading = {
  latitude: 6.795132,
  longitude: 79.900421,
  accuracyM: 18.5,
  capturedAt: '2026-08-13T05:30:14.000Z',
  mocked: false,
};
const backendAttempt = {
  verificationAttemptId: '50000000-0000-0000-0000-000000000001',
  attemptNumber: 1,
  decision: 'PASSED',
  distanceM: 18.7,
  allowedRadiusM: 70,
  nextStep: 'FACE_VERIFICATION',
  reason: null,
};

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

function buildServiceWithToken(token: string | undefined) {
  return new CoreApiGeofenceValidationService(
    new CoreApiClient({
      baseUrl: 'http://10.0.2.2:8000',
      getAccessToken: () => token,
    }),
  );
}

function buildService() {
  return buildServiceWithToken(accessToken);
}

describe('CoreApiGeofenceValidationService', () => {
  beforeEach(() => {
    jest.spyOn(console, 'warn').mockImplementation(() => undefined);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('posts only the fresh reading to the protected session endpoint', async () => {
    const fetchMock = jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(jsonResponse(200, backendAttempt));

    await buildService().submitAttempt({ sessionId, reading });

    expect(fetchMock).toHaveBeenCalledWith(
      `http://10.0.2.2:8000/api/v1/attendance-sessions/${sessionId}/geofence-attempts`,
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        }),
        body: JSON.stringify({
          latitude: reading.latitude,
          longitude: reading.longitude,
          accuracyM: reading.accuracyM,
          capturedAt: reading.capturedAt,
          mocked: reading.mocked,
        }),
      }),
    );
    const requestBody = JSON.parse(
      (fetchMock.mock.calls[0]?.[1] as RequestInit).body as string,
    );
    expect(requestBody).not.toHaveProperty('studentId');
    expect(requestBody).not.toHaveProperty('decision');
    expect(requestBody).not.toHaveProperty('allowedRadiusM');
  });

  test('returns the server decision without recalculating it', async () => {
    jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(jsonResponse(200, backendAttempt));

    await expect(
      buildService().submitAttempt({ sessionId, reading }),
    ).resolves.toEqual({ status: 'completed', attempt: backendAttempt });
  });

  test.each([
    [401, 'unauthenticated'],
    [403, 'forbidden'],
    [404, 'not-found'],
    [409, 'conflict'],
    [422, 'invalid-request'],
    [500, 'server-error'],
  ])('maps HTTP %i to %s', async (httpStatus, expectedStatus) => {
    jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(jsonResponse(httpStatus, {}));

    await expect(
      buildService().submitAttempt({ sessionId, reading }),
    ).resolves.toEqual({ status: expectedStatus });
  });

  test('maps a network failure without returning mock success', async () => {
    jest
      .spyOn(global, 'fetch')
      .mockRejectedValue(new Error('Network request failed'));

    await expect(
      buildService().submitAttempt({ sessionId, reading }),
    ).resolves.toEqual({ status: 'network-error' });
  });

  test('rejects an unrecognized success response', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(
      jsonResponse(200, {
        ...backendAttempt,
        decision: 'SURPRISING',
      }),
    );

    await expect(
      buildService().submitAttempt({ sessionId, reading }),
    ).resolves.toEqual({ status: 'server-error' });
  });

  test('rejects an internally inconsistent success response', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(
      jsonResponse(200, {
        ...backendAttempt,
        nextStep: 'NONE',
      }),
    );

    await expect(
      buildService().submitAttempt({ sessionId, reading }),
    ).resolves.toEqual({ status: 'server-error' });
  });

  test('does not call the backend without an access token', async () => {
    const fetchMock = jest.spyOn(global, 'fetch');

    await expect(
      buildServiceWithToken(undefined).submitAttempt({ sessionId, reading }),
    ).resolves.toEqual({ status: 'unauthenticated' });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
