import { afterEach, expect, jest, test } from '@jest/globals';

import { CoreApiClient } from '../../../services/api/coreApiClient';
import { CoreApiAttendanceFaceVerificationService } from '../services/coreApiAttendanceFaceVerificationService';


const token = 'header.payload.signature';
const baseUrl = 'http://10.0.2.2:8000';

function response(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: async () => body,
  } as Response;
}

function conflictResponse(): Response {
  return {
    ok: false,
    status: 409,
  } as Response;
}

function invalidLivenessResponse(): Response {
  return {
    ok: false,
    status: 422,
    json: async () => ({
      detail: {
        code: 'FACE_VERIFICATION_INVALID_REQUEST',
        message: 'Liveness evidence is invalid.',
      },
    }),
  } as Response;
}

function serviceUnavailableResponse(): Response {
  return {
    ok: false,
    status: 503,
    json: async () => ({
      detail: {
        code: 'FACE_VERIFICATION_SERVICE_ERROR',
        message: 'Face verification service is unavailable.',
      },
    }),
  } as Response;
}

afterEach(() => {
  jest.restoreAllMocks();
});

test('loads whether face verification already passed', async () => {
  jest.spyOn(global, 'fetch').mockResolvedValue(
    response({ status: 'passed' }),
  );
  const service = new CoreApiAttendanceFaceVerificationService(
    new CoreApiClient({ baseUrl, getAccessToken: () => token }),
  );

  await expect(service.getProgress('attendance-session')).resolves.toBe(
    'passed',
  );
});

test('uploads an attendance face capture to the Core API', async () => {
  const fetchMock = jest.spyOn(global, 'fetch').mockResolvedValue(
    response({
      status: 'success',
      attemptNumber: 1,
      canRetry: false,
    }),
  );
  const service = new CoreApiAttendanceFaceVerificationService(
    new CoreApiClient({
      baseUrl,
      getAccessToken: () => token,
      timeoutMs: 30_000,
    }),
  );

  await expect(
    service.verifyFace({
      sessionId: 'session/with space',
      capture: { uri: 'file:///capture.jpg' },
    }),
  ).resolves.toEqual({ status: 'success' });

  expect(fetchMock).toHaveBeenCalledWith(
    `${baseUrl}/api/v1/attendance-sessions/session%2Fwith%20space/face-verifications`,
    expect.objectContaining({
      method: 'POST',
      body: expect.any(FormData),
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${token}`,
      },
    }),
  );
  const requestBody = fetchMock.mock.calls[0][1]?.body as FormData;
  expect(requestBody.get('liveness')).toBeNull();
});

test('uploads canonical liveness evidence with the final face capture', async () => {
  const fetchMock = jest.spyOn(global, 'fetch').mockResolvedValue(
    response({
      status: 'success',
      attemptNumber: 1,
      canRetry: false,
    }),
  );
  const service = new CoreApiAttendanceFaceVerificationService(
    new CoreApiClient({ baseUrl, getAccessToken: () => token }),
  );
  const livenessEvidence = {
    version: 1 as const,
    method: 'mlkit_challenge' as const,
    passed: true as const,
    challenges: ['turn_left', 'eyes_closed_hold'] as const,
    startedAt: '2026-09-23T08:00:00.000Z',
    completedAt: '2026-09-23T08:00:05.000Z',
    engine: 'uniattend-mobile-liveness' as const,
  };

  await service.verifyFace({
    sessionId: 'attendance-session',
    capture: { uri: 'file:///capture.jpg' },
    livenessEvidence,
  });

  const requestBody = fetchMock.mock.calls[0][1]?.body as FormData;
  expect(requestBody.get('liveness')).toBe(
    JSON.stringify(livenessEvidence),
  );
});

test('preserves whether another face attempt is allowed', async () => {
  jest.spyOn(global, 'fetch').mockResolvedValue(
    response({
      status: 'face_not_detected',
      attemptNumber: 3,
      canRetry: false,
    }),
  );
  const service = new CoreApiAttendanceFaceVerificationService(
    new CoreApiClient({ baseUrl, getAccessToken: () => token }),
  );

  await expect(
    service.verifyFace({
      sessionId: 'attendance-session',
      capture: { uri: 'file:///capture.jpg' },
    }),
  ).resolves.toEqual({
    status: 'face_not_detected',
    canRetry: false,
  });
});

test.each([
  {
    apiStatus: 'multiple_faces',
    expected: { status: 'multiple_faces', canRetry: true },
  },
  {
    apiStatus: 'verification_failure',
    expected: { status: 'verification_failure', canRetry: true },
  },
] as const)(
  'preserves the existing $apiStatus biometric outcome',
  async ({ apiStatus, expected }) => {
    jest.spyOn(global, 'fetch').mockResolvedValue(
      response({
        status: apiStatus,
        attemptNumber: 1,
        canRetry: true,
      }),
    );
    const service = new CoreApiAttendanceFaceVerificationService(
      new CoreApiClient({ baseUrl, getAccessToken: () => token }),
    );

    await expect(
      service.verifyFace({
        sessionId: 'attendance-session',
        capture: { uri: 'file:///capture.jpg' },
      }),
    ).resolves.toEqual(expected);
  },
);

test('keeps a network failure retryable and separate from liveness rejection', async () => {
  jest.spyOn(console, 'warn').mockImplementation(() => undefined);
  jest.spyOn(global, 'fetch').mockRejectedValue(new Error('offline'));
  const service = new CoreApiAttendanceFaceVerificationService(
    new CoreApiClient({ baseUrl, getAccessToken: () => token }),
  );

  await expect(
    service.verifyFace({
      sessionId: 'attendance-session',
      capture: { uri: 'file:///capture.jpg' },
    }),
  ).resolves.toEqual({
    status: 'verification_failure',
    canRetry: true,
  });
});

test('treats a closed verification attempt as terminal', async () => {
  jest.spyOn(console, 'warn').mockImplementation(() => undefined);
  jest.spyOn(global, 'fetch').mockResolvedValue(conflictResponse());
  const service = new CoreApiAttendanceFaceVerificationService(
    new CoreApiClient({ baseUrl, getAccessToken: () => token }),
  );

  await expect(
    service.verifyFace({
      sessionId: 'attendance-session',
      capture: { uri: 'file:///capture.jpg' },
    }),
  ).resolves.toEqual({
    status: 'verification_failure',
    canRetry: false,
  });
});

test('maps the existing 422 liveness error to a retryable liveness failure', async () => {
  jest.spyOn(console, 'warn').mockImplementation(() => undefined);
  jest.spyOn(global, 'fetch').mockResolvedValue(invalidLivenessResponse());
  const service = new CoreApiAttendanceFaceVerificationService(
    new CoreApiClient({ baseUrl, getAccessToken: () => token }),
  );

  await expect(
    service.verifyFace({
      sessionId: 'attendance-session',
      capture: { uri: 'file:///capture.jpg' },
    }),
  ).resolves.toEqual({
    status: 'liveness_failure',
    canRetry: true,
  });
});

test('maps the existing 503 service error to a retryable unavailable result', async () => {
  jest.spyOn(console, 'warn').mockImplementation(() => undefined);
  jest.spyOn(global, 'fetch').mockResolvedValue(serviceUnavailableResponse());
  const service = new CoreApiAttendanceFaceVerificationService(
    new CoreApiClient({ baseUrl, getAccessToken: () => token }),
  );

  await expect(
    service.verifyFace({
      sessionId: 'attendance-session',
      capture: { uri: 'file:///capture.jpg' },
    }),
  ).resolves.toEqual({
    status: 'service_unavailable',
    canRetry: true,
  });
});
