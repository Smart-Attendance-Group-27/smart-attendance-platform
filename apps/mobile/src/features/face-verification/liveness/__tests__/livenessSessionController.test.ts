import { describe, expect, jest, test } from '@jest/globals';

import type {
  ExpoCameraCaptureSource,
  LivenessCaptureSample,
} from '../expoCameraCaptureSource';
import {
  createLivenessSessionController,
  type LivenessSessionController,
  type LivenessSessionSnapshot,
} from '../livenessSessionController';
import type { NormalizedFaceObservation } from '../livenessTypes';

function observation(
  timestampMs: number,
  overrides: Partial<NormalizedFaceObservation> = {},
): NormalizedFaceObservation {
  return {
    timestampMs,
    faceCount: 1,
    yawDegrees: 0,
    leftEyeOpenProbability: 1,
    rightEyeOpenProbability: 1,
    faceAreaRatio: 0.2,
    ...overrides,
  };
}

function createMockSample(
  value: NormalizedFaceObservation,
  index = 0,
): LivenessCaptureSample & {
  photo: LivenessCaptureSample['photo'] & {
    delete: ReturnType<typeof jest.fn<() => Promise<void>>>;
  };
} {
  return {
    observation: value,
    photo: {
      uri: `file:///liveness-${index}.jpg`,
      delete: jest.fn(async () => undefined),
    },
  };
}

function createSequenceSource(
  observations: readonly NormalizedFaceObservation[],
  setNow: (timestampMs: number) => void,
) {
  let index = 0;
  const samples = observations.map((value, sampleIndex) =>
    createMockSample(value, sampleIndex));
  const captureSample = jest.fn(async () => {
    const next = samples[index];
    index += 1;
    if (!next) throw new Error('No mocked observation remains.');
    setNow(next.observation.timestampMs);
    return next;
  });

  return {
    captureSource: { captureSample } satisfies ExpoCameraCaptureSource,
    captureSample,
    samples,
  };
}

function passingObservations(): readonly NormalizedFaceObservation[] {
  return [
    observation(1_000, { yawDegrees: 30 }),
    observation(1_300, { yawDegrees: 30 }),
    observation(1_400, { yawDegrees: -30 }),
    observation(1_700, { yawDegrees: -30 }),
    observation(1_800),
    observation(2_300),
  ];
}

function waitForSnapshot(
  controller: LivenessSessionController,
  predicate: (snapshot: LivenessSessionSnapshot) => boolean,
): Promise<LivenessSessionSnapshot> {
  const current = controller.getSnapshot();
  if (predicate(current)) return Promise.resolve(current);

  return new Promise((resolve) => {
    const unsubscribe = controller.subscribe(() => {
      const next = controller.getSnapshot();
      if (!predicate(next)) return;
      unsubscribe();
      resolve(next);
    });
  });
}

describe('createLivenessSessionController', () => {
  test('retains only the frontal image that completes a successful session', async () => {
    let currentTime = 1_000;
    const sequence = createSequenceSource(passingObservations(), (timestampMs) => {
      currentTime = timestampMs;
    });
    const controller = createLivenessSessionController({
      captureSource: sequence.captureSource,
      now: () => currentTime,
      random: () => 0,
    });

    controller.start();
    const result = await waitForSnapshot(
      controller,
      (snapshot) => snapshot.status === 'passed',
    );

    expect(result.completedChallengeCount).toBe(2);
    expect(result.challengeCount).toBe(2);
    expect(result.activeChallenge).toBeNull();
    expect(result.finalPhoto).toEqual({ uri: 'file:///liveness-5.jpg' });
    expect(result.livenessEvidence).toEqual({
      version: 1,
      method: 'mlkit_challenge',
      passed: true,
      challenges: ['turn_left', 'turn_right'],
      startedAt: '1970-01-01T00:00:01.000Z',
      completedAt: '1970-01-01T00:00:02.300Z',
      engine: 'uniattend-mobile-liveness',
    });
    expect(result.sessionState?.challenges.map(({ challenge }) => challenge))
      .toEqual(['turn_left', 'turn_right']);
    sequence.samples.slice(0, -1).forEach(({ photo }) => {
      expect(photo.delete).toHaveBeenCalledTimes(1);
    });
    expect(sequence.samples[5].photo.delete).not.toHaveBeenCalled();
    expect(sequence.captureSample).toHaveBeenCalledTimes(6);

    const claimedPhoto = controller.claimFinalPhoto();
    expect(claimedPhoto?.uri).toBe('file:///liveness-5.jpg');
    expect(controller.claimFinalPhoto()).toBeNull();
  });

  test('failed session returns no image and deletes its failed capture', async () => {
    let currentTime = 1_000;
    const sequence = createSequenceSource([
      observation(1_100, {
        faceCount: 0,
        faceAreaRatio: 0,
        yawDegrees: null,
      }),
    ], (timestampMs) => {
      currentTime = timestampMs;
    });
    const controller = createLivenessSessionController({
      captureSource: sequence.captureSource,
      now: () => currentTime,
      random: () => 0,
    });

    controller.start();
    const result = await waitForSnapshot(
      controller,
      (snapshot) => snapshot.status === 'failed',
    );

    expect(result.failure).toEqual({
      kind: 'observation',
      reason: 'no_face',
    });
    expect(result.finalPhoto).toBeNull();
    expect(result.livenessEvidence).toBeNull();
    expect(controller.claimFinalPhoto()).toBeNull();
    expect(sequence.samples[0].photo.delete).toHaveBeenCalledTimes(1);
  });

  test('exposes S2 challenge timeout and deletes the timed-out capture', async () => {
    let currentTime = 1_000;
    const sample = createMockSample(observation(7_001));
    const captureSample = jest.fn(async () => {
      currentTime = 7_001;
      return sample;
    });
    const controller = createLivenessSessionController({
      captureSource: { captureSample },
      now: () => currentTime,
      random: () => 0,
    });

    controller.start();
    const result = await waitForSnapshot(
      controller,
      (snapshot) => snapshot.status === 'timed_out',
    );

    expect(result.timeoutReason).toBe('challenge_timeout');
    expect(result.finalPhoto).toBeNull();
    expect(result.livenessEvidence).toBeNull();
    expect(sample.photo.delete).toHaveBeenCalledTimes(1);
    expect(captureSample).toHaveBeenCalledTimes(1);
  });

  test('exposes S2 whole-session timeout and deletes the timed-out capture', async () => {
    let currentTime = 1_000;
    const sample = createMockSample(observation(26_001));
    const captureSample = jest.fn(async () => {
      currentTime = 26_001;
      return sample;
    });
    const controller = createLivenessSessionController({
      captureSource: { captureSample },
      now: () => currentTime,
      random: () => 0,
    });

    controller.start();
    const result = await waitForSnapshot(
      controller,
      (snapshot) => snapshot.status === 'timed_out',
    );

    expect(result.timeoutReason).toBe('session_timeout');
    expect(result.finalPhoto).toBeNull();
    expect(result.livenessEvidence).toBeNull();
    expect(sample.photo.delete).toHaveBeenCalledTimes(1);
    expect(captureSample).toHaveBeenCalledTimes(1);
  });

  test('restart replaces the session and deletes a stale in-flight image', async () => {
    let currentTime = 1_000;
    let resolveFirst: ((value: LivenessCaptureSample) => void) | undefined;
    const staleSample = createMockSample(
      observation(1_100, { yawDegrees: 30 }),
    );
    const failedSample = createMockSample(observation(2_100, {
      faceCount: 0,
      faceAreaRatio: 0,
      yawDegrees: null,
    }), 1);
    const firstCapture = new Promise<LivenessCaptureSample>((resolve) => {
      resolveFirst = resolve;
    });
    const captureSample = jest.fn<ExpoCameraCaptureSource['captureSample']>()
      .mockImplementationOnce(() => firstCapture)
      .mockImplementationOnce(async () => {
        currentTime = 2_100;
        return failedSample;
      });
    const controller = createLivenessSessionController({
      captureSource: { captureSample },
      now: () => currentTime,
      random: () => 0,
    });

    controller.start();
    currentTime = 2_000;
    controller.restart();
    resolveFirst?.(staleSample);

    const result = await waitForSnapshot(
      controller,
      (snapshot) => snapshot.status === 'failed',
    );
    expect(result.sessionState?.startedAtMs).toBe(2_000);
    expect(result.finalPhoto).toBeNull();
    expect(result.livenessEvidence).toBeNull();
    expect(controller.claimFinalPhoto()).toBeNull();
    expect(staleSample.photo.delete).toHaveBeenCalledTimes(1);
    expect(failedSample.photo.delete).toHaveBeenCalledTimes(1);
    expect(captureSample).toHaveBeenCalledTimes(2);
  });

  test('restart clears and deletes a previously retained final image', async () => {
    let currentTime = 1_000;
    const sequence = createSequenceSource(passingObservations(), (timestampMs) => {
      currentTime = timestampMs;
    });
    const controller = createLivenessSessionController({
      captureSource: sequence.captureSource,
      now: () => currentTime,
      random: () => 0,
    });

    controller.start();
    await waitForSnapshot(controller, ({ status }) => status === 'passed');
    expect(controller.getSnapshot().finalPhoto).not.toBeNull();

    currentTime = 3_000;
    controller.restart();
    await waitForSnapshot(controller, ({ status }) => status === 'failed');

    expect(controller.getSnapshot().finalPhoto).toBeNull();
    expect(controller.getSnapshot().livenessEvidence).toBeNull();
    expect(controller.claimFinalPhoto()).toBeNull();
    expect(sequence.samples[5].photo.delete).toHaveBeenCalledTimes(1);
  });

  test('cancelled session returns no image and deletes its in-flight capture', async () => {
    let resolveCapture: ((value: LivenessCaptureSample) => void) | undefined;
    const staleSample = createMockSample(
      observation(1_100, { yawDegrees: 30 }),
    );
    const pendingCapture = new Promise<LivenessCaptureSample>((resolve) => {
      resolveCapture = resolve;
    });
    const captureSample = jest.fn(() => pendingCapture);
    const controller = createLivenessSessionController({
      captureSource: { captureSample },
      now: () => 1_000,
      random: () => 0,
    });

    controller.start();
    controller.cancel();
    resolveCapture?.(staleSample);
    await pendingCapture;
    await Promise.resolve();

    expect(controller.getSnapshot().status).toBe('cancelled');
    expect(controller.getSnapshot().activeChallenge).toBeNull();
    expect(controller.getSnapshot().finalPhoto).toBeNull();
    expect(controller.getSnapshot().livenessEvidence).toBeNull();
    expect(controller.claimFinalPhoto()).toBeNull();
    expect(staleSample.photo.delete).toHaveBeenCalledTimes(1);
    expect(captureSample).toHaveBeenCalledTimes(1);
  });

  test('dispose stops processing and deletes an in-flight capture', async () => {
    let resolveCapture: ((value: LivenessCaptureSample) => void) | undefined;
    const staleSample = createMockSample(observation(1_100));
    const pendingCapture = new Promise<LivenessCaptureSample>((resolve) => {
      resolveCapture = resolve;
    });
    const captureSample = jest.fn(() => pendingCapture);
    const controller = createLivenessSessionController({
      captureSource: { captureSample },
      now: () => 1_000,
      random: () => 0,
    });

    controller.start();
    controller.dispose();
    resolveCapture?.(staleSample);
    await pendingCapture;
    await Promise.resolve();

    expect(controller.getSnapshot().status).toBe('cancelled');
    expect(staleSample.photo.delete).toHaveBeenCalledTimes(1);
    expect(captureSample).toHaveBeenCalledTimes(1);
  });

  test('cancellation during temporary-image cleanup cannot restart processing', async () => {
    let resolveDelete: (() => void) | undefined;
    const pendingDelete = new Promise<void>((resolve) => {
      resolveDelete = resolve;
    });
    const sample = createMockSample(observation(1_100));
    sample.photo.delete.mockImplementation(() => pendingDelete);
    const captureSample = jest.fn(async () => sample);
    const controller = createLivenessSessionController({
      captureSource: { captureSample },
      now: () => 1_100,
      random: () => 0,
    });

    controller.start();
    await Promise.resolve();
    expect(sample.photo.delete).toHaveBeenCalledTimes(1);

    controller.cancel();
    resolveDelete?.();
    await pendingDelete;
    await Promise.resolve();
    await Promise.resolve();

    expect(controller.getSnapshot().status).toBe('cancelled');
    expect(controller.getSnapshot().livenessEvidence).toBeNull();
    expect(captureSample).toHaveBeenCalledTimes(1);
  });

  test('cleanup rejection after cancellation cannot overwrite cancelled state', async () => {
    let rejectDelete: ((error: Error) => void) | undefined;
    const pendingDelete = new Promise<void>((_resolve, reject) => {
      rejectDelete = reject;
    });
    const sample = createMockSample(observation(1_100));
    sample.photo.delete.mockImplementation(() => pendingDelete);
    const captureSample = jest.fn(async () => sample);
    const controller = createLivenessSessionController({
      captureSource: { captureSample },
      now: () => 1_100,
      random: () => 0,
    });

    controller.start();
    await Promise.resolve();
    expect(sample.photo.delete).toHaveBeenCalledTimes(1);

    controller.cancel();
    rejectDelete?.(new Error('cleanup failed after cancellation'));
    await expect(pendingDelete).rejects.toThrow('cleanup failed after cancellation');
    await Promise.resolve();
    await Promise.resolve();

    expect(controller.getSnapshot().status).toBe('cancelled');
    expect(controller.getSnapshot().failure).toBeNull();
    expect(captureSample).toHaveBeenCalledTimes(1);
  });

  test('cancellation during final-image cleanup prevents a restarted capture', async () => {
    let currentTime = 1_000;
    const sequence = createSequenceSource(passingObservations(), (timestampMs) => {
      currentTime = timestampMs;
    });
    const controller = createLivenessSessionController({
      captureSource: sequence.captureSource,
      now: () => currentTime,
      random: () => 0,
    });

    controller.start();
    await waitForSnapshot(controller, ({ status }) => status === 'passed');

    let resolveDelete: (() => void) | undefined;
    const pendingDelete = new Promise<void>((resolve) => {
      resolveDelete = resolve;
    });
    sequence.samples[5].photo.delete.mockImplementation(() => pendingDelete);
    currentTime = 3_000;
    controller.restart();
    expect(controller.getSnapshot().livenessEvidence).toBeNull();
    expect(sequence.samples[5].photo.delete).toHaveBeenCalledTimes(1);

    controller.cancel();
    resolveDelete?.();
    await pendingDelete;
    await Promise.resolve();
    await Promise.resolve();

    expect(controller.getSnapshot().status).toBe('cancelled');
    expect(controller.getSnapshot().finalPhoto).toBeNull();
    expect(controller.getSnapshot().livenessEvidence).toBeNull();
    expect(sequence.captureSample).toHaveBeenCalledTimes(6);
  });

  test('never overlaps camera observation requests', async () => {
    let concurrentCaptures = 0;
    let maximumConcurrentCaptures = 0;
    const resolvers: ((value: LivenessCaptureSample) => void)[] = [];
    const captureSample = jest.fn(() => {
      concurrentCaptures += 1;
      maximumConcurrentCaptures = Math.max(
        maximumConcurrentCaptures,
        concurrentCaptures,
      );
      return new Promise<LivenessCaptureSample>((resolve) => {
        resolvers.push((value) => {
          concurrentCaptures -= 1;
          resolve(value);
        });
      });
    });
    let currentTime = 1_000;
    const controller = createLivenessSessionController({
      captureSource: { captureSample },
      now: () => currentTime,
      random: () => 0,
    });

    controller.start();
    expect(captureSample).toHaveBeenCalledTimes(1);

    currentTime = 1_100;
    resolvers[0](createMockSample(observation(1_100)));
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    expect(captureSample).toHaveBeenCalledTimes(2);
    expect(maximumConcurrentCaptures).toBe(1);

    controller.cancel();
    currentTime = 1_200;
    resolvers[1](createMockSample(observation(1_200), 1));
    await Promise.resolve();
    expect(captureSample).toHaveBeenCalledTimes(2);
  });
});
