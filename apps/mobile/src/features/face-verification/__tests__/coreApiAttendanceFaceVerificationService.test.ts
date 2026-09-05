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

afterEach(() => {
  jest.restoreAllMocks();
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
