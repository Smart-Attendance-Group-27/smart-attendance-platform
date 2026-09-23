import { describe, expect, test } from '@jest/globals';
import type { Face } from '@react-native-ml-kit/face-detection';

import { normalizeMlKitFaceObservation } from '../mlKitObservation';

function createFace(overrides: Partial<Face> = {}): Face {
  return {
    frame: {
      height: 200,
      left: 40,
      top: 50,
      width: 100,
    },
    rotationX: 0,
    rotationY: 0,
    rotationZ: 0,
    ...overrides,
  };
}

describe('normalizeMlKitFaceObservation', () => {
  test('normalizes a single face and computes its image-area ratio', () => {
    const observation = normalizeMlKitFaceObservation({
      faces: [
        createFace({
          leftEyeOpenProbability: 0.85,
          rightEyeOpenProbability: 0.9,
          rotationY: 32,
          trackingID: 17,
        }),
      ],
      imageHeight: 500,
      imageWidth: 400,
      timestampMs: 1_500,
    });

    expect(observation).toEqual({
      timestampMs: 1_500,
      faceCount: 1,
      yawDegrees: 32,
      leftEyeOpenProbability: 0.85,
      rightEyeOpenProbability: 0.9,
      faceAreaRatio: 0.1,
      trackingId: 17,
    });
  });

  test.each([
    { rotationY: 25, expectedYaw: 25 },
    { rotationY: -25, expectedYaw: -25 },
  ])('preserves the established front-camera yaw sign', ({
    rotationY,
    expectedYaw,
  }) => {
    const observation = normalizeMlKitFaceObservation({
      faces: [createFace({ rotationY })],
      imageHeight: 500,
      imageWidth: 400,
      timestampMs: 2_000,
    });

    expect(observation.yawDegrees).toBe(expectedYaw);
  });

  test('uses null for unavailable measurements and omits an absent tracking ID', () => {
    const observation = normalizeMlKitFaceObservation({
      faces: [createFace()],
      imageHeight: 500,
      imageWidth: 400,
      timestampMs: 2_500,
    });

    expect(observation.leftEyeOpenProbability).toBeNull();
    expect(observation.rightEyeOpenProbability).toBeNull();
    expect(observation).not.toHaveProperty('trackingId');
  });

  test.each([
    { faces: [] },
    { faces: [createFace(), createFace()] },
  ])(
    'does not select face measurements unless exactly one face is present',
    ({ faces }) => {
      const observation = normalizeMlKitFaceObservation({
        faces,
        imageHeight: 500,
        imageWidth: 400,
        timestampMs: 3_000,
      });

      expect(observation).toEqual({
        timestampMs: 3_000,
        faceCount: faces.length,
        yawDegrees: null,
        leftEyeOpenProbability: null,
        rightEyeOpenProbability: null,
        faceAreaRatio: 0,
      });
    },
  );

  test.each([
    { imageHeight: 500, imageWidth: 0 },
    { imageHeight: Number.NaN, imageWidth: 400 },
  ])('rejects invalid image dimensions', ({ imageHeight, imageWidth }) => {
    expect(() =>
      normalizeMlKitFaceObservation({
        faces: [createFace()],
        imageHeight,
        imageWidth,
        timestampMs: 3_500,
      }),
    ).toThrow(RangeError);
  });
});
