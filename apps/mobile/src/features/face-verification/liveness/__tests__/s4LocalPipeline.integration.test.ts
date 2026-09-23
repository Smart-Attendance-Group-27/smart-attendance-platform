import { describe, expect, jest, test } from '@jest/globals';
import type { Face } from '@react-native-ml-kit/face-detection';

import { createExpoCameraCaptureSource } from '../expoCameraCaptureSource';
import {
  createLivenessSessionController,
  type LivenessSessionController,
  type LivenessSessionSnapshot,
} from '../livenessSessionController';

type PipelineStep = {
  readonly timestampMs: number;
  readonly yawDegrees: number;
  readonly leftEyeOpenProbability: number;
  readonly rightEyeOpenProbability: number;
};

const PIPELINE_STEPS: readonly PipelineStep[] = [
  {
    timestampMs: 1_100,
    yawDegrees: -30,
    leftEyeOpenProbability: 1,
    rightEyeOpenProbability: 1,
  },
  {
    timestampMs: 1_400,
    yawDegrees: -30,
    leftEyeOpenProbability: 1,
    rightEyeOpenProbability: 1,
  },
  {
    timestampMs: 1_500,
    yawDegrees: 0,
    leftEyeOpenProbability: 0.05,
    rightEyeOpenProbability: 0.05,
  },
  {
    timestampMs: 2_300,
    yawDegrees: 0,
    leftEyeOpenProbability: 0.05,
    rightEyeOpenProbability: 0.05,
  },
  {
    timestampMs: 2_400,
    yawDegrees: 0,
    leftEyeOpenProbability: 1,
    rightEyeOpenProbability: 1,
  },
  {
    timestampMs: 2_900,
    yawDegrees: 0,
    leftEyeOpenProbability: 1,
    rightEyeOpenProbability: 1,
  },
];

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

describe('S4 local pipeline integration', () => {
  test('moves mocked camera and ML Kit results through S2 to a retained photo and evidence', async () => {
    let currentTime = 1_000;
    let captureIndex = 0;
    let activeCaptures = 0;
    let activeDetections = 0;
    let maximumCaptures = 0;
    let maximumDetections = 0;
    let captureStartedDuringDetection = false;
    const deletedUris: string[] = [];

    const takePictureAsync = jest.fn(async () => {
      if (activeDetections > 0) captureStartedDuringDetection = true;
      activeCaptures += 1;
      maximumCaptures = Math.max(maximumCaptures, activeCaptures);

      const index = captureIndex;
      const step = PIPELINE_STEPS[index];
      captureIndex += 1;
      if (!step) throw new Error('No mocked camera frame remains.');
      currentTime = step.timestampMs;
      await Promise.resolve();
      activeCaptures -= 1;

      return {
        height: 500,
        uri: `file:///s4-pipeline-${index}.jpg`,
        width: 400,
      };
    });
    const detectFaces = jest.fn(async (uri: string): Promise<readonly Face[]> => {
      activeDetections += 1;
      maximumDetections = Math.max(maximumDetections, activeDetections);
      const index = Number(uri.match(/-(\d+)\.jpg$/)?.[1]);
      const step = PIPELINE_STEPS[index];
      if (!step) throw new Error(`No mocked ML Kit result exists for ${uri}.`);
      await Promise.resolve();
      activeDetections -= 1;

      return [{
        frame: { height: 200, left: 100, top: 100, width: 200 },
        rotationX: 0,
        rotationY: step.yawDegrees,
        rotationZ: 0,
        leftEyeOpenProbability: step.leftEyeOpenProbability,
        rightEyeOpenProbability: step.rightEyeOpenProbability,
      }];
    });
    const deleteImage = jest.fn(async (uri: string) => {
      deletedUris.push(uri);
    });
    const captureSource = createExpoCameraCaptureSource({
      deleteImage,
      detectFaces,
      getCamera: () => ({ takePictureAsync }),
      now: () => currentTime,
      platform: 'android',
    });
    const randomValues = [0, 0.999];
    const controller = createLivenessSessionController({
      captureSource,
      now: () => currentTime,
      random: () => randomValues.shift() ?? 0,
    });

    controller.start();
    const result = await waitForSnapshot(
      controller,
      ({ status }) => status === 'passed',
    );

    expect(result.sessionState?.challenges.map(({ challenge }) => challenge))
      .toEqual(['turn_left', 'eyes_closed_hold']);
    expect(new Set(result.livenessEvidence?.challenges).size).toBe(2);
    expect(result.completedChallengeCount).toBe(2);
    expect(result.sessionState?.frontalConfirmation.progress).toBe('completed');
    expect(result.finalPhoto).toEqual({ uri: 'file:///s4-pipeline-5.jpg' });
    expect(result.livenessEvidence).toEqual({
      version: 1,
      method: 'mlkit_challenge',
      passed: true,
      challenges: ['turn_left', 'eyes_closed_hold'],
      startedAt: '1970-01-01T00:00:01.000Z',
      completedAt: '1970-01-01T00:00:02.900Z',
      engine: 'uniattend-mobile-liveness',
    });
    expect(Date.parse(result.livenessEvidence!.startedAt))
      .toBeLessThanOrEqual(Date.parse(result.livenessEvidence!.completedAt));
    expect(takePictureAsync).toHaveBeenCalledTimes(PIPELINE_STEPS.length);
    expect(detectFaces).toHaveBeenCalledTimes(PIPELINE_STEPS.length);
    expect(maximumCaptures).toBe(1);
    expect(maximumDetections).toBe(1);
    expect(captureStartedDuringDetection).toBe(false);
    expect(deletedUris).toEqual([
      'file:///s4-pipeline-0.jpg',
      'file:///s4-pipeline-1.jpg',
      'file:///s4-pipeline-2.jpg',
      'file:///s4-pipeline-3.jpg',
      'file:///s4-pipeline-4.jpg',
    ]);

    const finalPhoto = controller.claimFinalPhoto();
    expect(finalPhoto?.uri).toBe('file:///s4-pipeline-5.jpg');
    expect(deletedUris).not.toContain('file:///s4-pipeline-5.jpg');
    await finalPhoto?.delete();
  });
});
