import {
  afterEach,
  beforeEach,
  describe,
  expect,
  jest,
  test,
} from '@jest/globals';

import {
  FaceVerificationApiService,
  resolveFaceVerificationApiBaseUrl,
} from '../services/faceVerificationApiService';

const accessToken = 'header.payload.signature';
const baseUrl = 'http://10.0.2.2:8001';

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

function buildServiceWithToken(token: string | undefined) {
  return new FaceVerificationApiService({
    baseUrl,
    getAccessToken: () => token,
  });
}

function buildService() {
  return buildServiceWithToken(accessToken);
}

describe('FaceVerificationApiService', () => {
  beforeEach(() => {
    jest.spyOn(console, 'warn').mockImplementation(() => undefined);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('gets readiness status with the logged-in student access token', async () => {
    const fetchMock = jest.spyOn(global, 'fetch').mockResolvedValue(
      jsonResponse(200, {
        status: 'not_checked',
        requiresReadinessCheck: true,
        checkedAt: null,
      }),
    );

    await buildService().getReadinessStatus();

    expect(fetchMock).toHaveBeenCalledWith(
      `${baseUrl}/api/v1/face-verification/readiness/status`,
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({
          Accept: 'application/json',
          Authorization: `Bearer ${accessToken}`,
        }),
      }),
    );
  });

  test('maps a valid readiness response', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(
      jsonResponse(200, {
        status: 'passed',
        requiresReadinessCheck: false,
        checkedAt: '2026-08-18T10:30:00Z',
      }),
    );

    await expect(buildService().getReadinessStatus()).resolves.toEqual({
      status: 'loaded',
      readiness: {
        status: 'passed',
        requiresReadinessCheck: false,
        checkedAt: '2026-08-18T10:30:00Z',
      },
    });
  });

  test.each([
    null,
    { status: 'unknown', requiresReadinessCheck: true, checkedAt: null },
    { status: 'not_checked', requiresReadinessCheck: 'yes', checkedAt: null },
    { status: 'failed', requiresReadinessCheck: true, checkedAt: 'invalid' },
  ])('rejects an invalid readiness response: %p', async (body) => {
    jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(jsonResponse(200, body));

    await expect(buildService().getReadinessStatus()).resolves.toEqual({
      status: 'server-error',
    });
  });

  test('does not call the endpoint without an access token', async () => {
    const fetchMock = jest.spyOn(global, 'fetch');

    await expect(
      buildServiceWithToken(undefined).getReadinessStatus(),
    ).resolves.toEqual({ status: 'unauthenticated' });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  test('propagates an authenticated API failure status', async () => {
    jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(jsonResponse(403, { detail: 'forbidden' }));

    await expect(buildService().getReadinessStatus()).resolves.toEqual({
      status: 'forbidden',
    });
  });

  test('uploads a readiness capture as authenticated multipart data', async () => {
    const fetchMock = jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(jsonResponse(200, { status: 'passed' }));

    await buildService().verifyReadiness('file:///face-capture.jpg');

    expect(fetchMock).toHaveBeenCalledWith(
      `${baseUrl}/api/v1/face-verification/readiness`,
      expect.objectContaining({
        method: 'POST',
        body: expect.any(FormData),
        headers: {
          Accept: 'application/json',
          Authorization: `Bearer ${accessToken}`,
        },
      }),
    );
  });

  test('keeps the readiness upload open while face processing exceeds the standard request timeout', async () => {
    jest.useFakeTimers();

    try {
      jest.spyOn(global, 'fetch').mockImplementation(
        (_input, init) =>
          new Promise<Response>((resolve, reject) => {
            const responseTimer = setTimeout(() => {
              resolve(jsonResponse(200, { status: 'passed' }));
            }, 6_000);

            init?.signal?.addEventListener('abort', () => {
              clearTimeout(responseTimer);
              reject(new Error('request aborted'));
            });
          }),
      );

      const result = buildService().verifyReadiness(
        'file:///face-capture.jpg',
      );

      await jest.advanceTimersByTimeAsync(6_000);

      await expect(result).resolves.toEqual({ status: 'success' });
    } finally {
      jest.useRealTimers();
    }
  });

  test.each([
    ['passed', 'success'],
    ['no_face', 'face_not_detected'],
    ['multiple_faces', 'multiple_faces'],
    ['failed', 'verification_failure'],
    ['low_quality', 'verification_failure'],
  ])(
    'maps readiness result %s to camera result %s',
    async (backendStatus, expectedStatus) => {
      jest
        .spyOn(global, 'fetch')
        .mockResolvedValue(jsonResponse(200, { status: backendStatus }));

      await expect(
        buildService().verifyReadiness('file:///face-capture.jpg'),
      ).resolves.toEqual({ status: expectedStatus });
    },
  );

  test('uses the configured face-verification API URL', () => {
    const previousValue =
      process.env.EXPO_PUBLIC_FACE_VERIFICATION_API_URL;
    process.env.EXPO_PUBLIC_FACE_VERIFICATION_API_URL =
      'http://192.168.1.5:8001/';

    try {
      expect(resolveFaceVerificationApiBaseUrl()).toBe(
        'http://192.168.1.5:8001',
      );
    } finally {
      process.env.EXPO_PUBLIC_FACE_VERIFICATION_API_URL = previousValue;
    }
  });
});
