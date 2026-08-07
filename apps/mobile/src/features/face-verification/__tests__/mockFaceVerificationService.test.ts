import {
  afterEach,
  describe,
  expect,
  jest,
  test,
} from '@jest/globals';

import type { FaceVerificationService } from '../services/faceVerificationService';
import { MockFaceVerificationService } from '../services/mockFaceVerificationService';
import type {
  FaceVerificationRequest,
  FaceVerificationResult,
} from '../types/faceVerification';

const verificationOutcomes: readonly FaceVerificationResult[] = [
  { status: 'success' },
  { status: 'face_not_detected' },
  { status: 'multiple_faces' },
  { status: 'liveness_failure' },
  { status: 'verification_failure' },
];

function createRequest(
  sessionId = 'attendance-session-active',
): FaceVerificationRequest {
  return {
    sessionId,
    capture: {
      uri: 'mock://face-capture',
    },
  };
}

describe('MockFaceVerificationService', () => {
  afterEach(() => {
    jest.useRealTimers();
  });

  test.each(verificationOutcomes)(
    'returns the configured $status outcome',
    async (configuredResult) => {
      const service = new MockFaceVerificationService({
        result: configuredResult,
      });

      await expect(service.verifyFace(createRequest())).resolves.toEqual(
        configuredResult,
      );
    },
  );

  test('implements the FaceVerificationService contract', async () => {
    const service: FaceVerificationService =
      new MockFaceVerificationService({
        result: { status: 'success' },
      });
    const request: FaceVerificationRequest = createRequest();

    const result: Promise<FaceVerificationResult> =
      service.verifyFace(request);

    await expect(result).resolves.toEqual({ status: 'success' });
  });

  test('accepts the application capture request without mutating it', async () => {
    const request: FaceVerificationRequest = createRequest();
    const originalRequest: FaceVerificationRequest = {
      sessionId: request.sessionId,
      capture: {
        uri: request.capture.uri,
      },
    };
    const service = new MockFaceVerificationService({
      result: { status: 'face_not_detected' },
    });

    await expect(service.verifyFace(request)).resolves.toEqual({
      status: 'face_not_detected',
    });
    expect(request).toEqual(originalRequest);
  });

  test('returns equivalent configured results for repeated requests', async () => {
    const service = new MockFaceVerificationService({
      result: { status: 'liveness_failure' },
    });

    await expect(
      service.verifyFace(createRequest('attendance-session-one')),
    ).resolves.toEqual({ status: 'liveness_failure' });
    await expect(
      service.verifyFace(createRequest('attendance-session-two')),
    ).resolves.toEqual({ status: 'liveness_failure' });
  });

  test('resolves immediately by default without timer advancement', async () => {
    jest.useFakeTimers();
    const service = new MockFaceVerificationService({
      result: { status: 'success' },
    });

    await expect(service.verifyFace(createRequest())).resolves.toEqual({
      status: 'success',
    });
    expect(jest.getTimerCount()).toBe(0);
  });

  test('keeps verification pending until the configured delay completes', async () => {
    jest.useFakeTimers();
    const service = new MockFaceVerificationService({
      result: { status: 'multiple_faces' },
      delayMs: 1000,
    });
    let hasSettled = false;

    const verification = service.verifyFace(createRequest()).then((result) => {
      hasSettled = true;
      return result;
    });

    await Promise.resolve();
    expect(hasSettled).toBe(false);

    await jest.advanceTimersByTimeAsync(999);
    expect(hasSettled).toBe(false);

    await jest.advanceTimersByTimeAsync(1);
    await expect(verification).resolves.toEqual({
      status: 'multiple_faces',
    });
    expect(hasSettled).toBe(true);
  });

  test('protects later calls from mutations to a returned result', async () => {
    const service = new MockFaceVerificationService({
      result: { status: 'success' },
    });

    const firstResult = await service.verifyFace(createRequest());
    Object.assign(firstResult, { status: 'verification_failure' });

    await expect(service.verifyFace(createRequest())).resolves.toEqual({
      status: 'success',
    });
  });
});
