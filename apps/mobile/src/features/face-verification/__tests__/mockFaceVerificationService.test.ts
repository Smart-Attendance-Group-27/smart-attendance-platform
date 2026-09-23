import {
  afterEach,
  describe,
  expect,
  jest,
  test,
} from '@jest/globals';

import type { FaceVerificationService } from '../services/faceVerificationService';
import { MockFaceVerificationService } from '../services/mockFaceVerificationService';
import type { LivenessEvidence } from '../liveness/livenessEvidence';
import type {
  FaceVerificationRequest,
  FaceVerificationResult,
} from '../types/faceVerification';

const livenessEvidence: LivenessEvidence = {
  version: 1,
  method: 'mlkit_challenge',
  passed: true,
  challenges: ['turn_left', 'eyes_closed_hold'],
  startedAt: '2026-09-23T08:00:00.000Z',
  completedAt: '2026-09-23T08:00:05.000Z',
  engine: 'uniattend-mobile-liveness',
};

const verificationScenarios: readonly {
  readonly scenario: string;
  readonly result: FaceVerificationResult;
}[] = [
  { scenario: 'successful verification', result: { status: 'success' } },
  {
    scenario: 'identity mismatch',
    result: { status: 'verification_failure', canRetry: true },
  },
  {
    scenario: 'liveness rejection',
    result: { status: 'liveness_failure', canRetry: true },
  },
  {
    scenario: 'service unavailable',
    result: { status: 'service_unavailable', canRetry: true },
  },
  { scenario: 'no face', result: { status: 'face_not_detected' } },
  { scenario: 'multiple faces', result: { status: 'multiple_faces' } },
];

function createRequest(
  sessionId = 'attendance-session-active',
  evidence?: LivenessEvidence,
): FaceVerificationRequest {
  return {
    sessionId,
    capture: {
      uri: 'mock://face-capture',
    },
    ...(evidence ? { livenessEvidence: evidence } : {}),
  };
}

describe('MockFaceVerificationService', () => {
  afterEach(() => {
    jest.useRealTimers();
  });

  test.each(verificationScenarios)(
    'simulates $scenario',
    async ({ result }) => {
      const service = new MockFaceVerificationService({
        result,
      });

      await expect(service.verifyFace(createRequest())).resolves.toEqual(
        result,
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
    const request: FaceVerificationRequest = createRequest(
      'attendance-session-active',
      livenessEvidence,
    );
    const originalRequest: FaceVerificationRequest = {
      sessionId: request.sessionId,
      capture: {
        uri: request.capture.uri,
      },
      livenessEvidence,
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
