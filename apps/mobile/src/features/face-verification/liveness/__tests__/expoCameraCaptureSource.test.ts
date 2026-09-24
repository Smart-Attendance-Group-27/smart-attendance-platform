import { describe, expect, jest, test } from '@jest/globals';
import type { Face } from '@react-native-ml-kit/face-detection';

import {
  createExpoCameraCaptureSource,
  LIVENESS_CAMERA_FACING,
  LivenessCaptureSourceError,
  type LivenessStillCamera,
} from '../expoCameraCaptureSource';

const capture = {
  height: 500,
  uri: 'file:///temporary-liveness.jpg',
  width: 400,
};

function createFace(overrides: Partial<Face> = {}): Face {
  return {
    frame: { height: 200, left: 20, top: 30, width: 100 },
    rotationX: 0,
    rotationY: 28,
    rotationZ: 0,
    ...overrides,
  };
}

async function expectCaptureError(
  promise: Promise<unknown>,
  code: LivenessCaptureSourceError['code'],
): Promise<void> {
  try {
    await promise;
    throw new Error('Expected the liveness capture source to reject.');
  } catch (error) {
    expect(error).toBeInstanceOf(LivenessCaptureSourceError);
    expect((error as LivenessCaptureSourceError).code).toBe(code);
  }
}

describe('createExpoCameraCaptureSource', () => {
  test('uses the front camera contract and produces a normalized observation', async () => {
    const takePictureAsync = jest.fn(async () => capture);
    const detectFaces = jest.fn(async () => [
      createFace({
        leftEyeOpenProbability: 0.8,
        rightEyeOpenProbability: 0.9,
      }),
    ]);
    const deleteImage = jest.fn(async () => undefined);
    const source = createExpoCameraCaptureSource({
      deleteImage,
      detectFaces,
      getCamera: () => ({ takePictureAsync }),
      now: () => 4_000,
      platform: 'android',
    });

    const sample = await source.captureSample();
    expect(sample.observation).toEqual({
      timestampMs: 4_000,
      faceCount: 1,
      yawDegrees: -28,
      leftEyeOpenProbability: 0.8,
      rightEyeOpenProbability: 0.9,
      faceAreaRatio: 0.1,
    });
    expect(LIVENESS_CAMERA_FACING).toBe('front');
    expect(takePictureAsync).toHaveBeenCalledWith({ quality: 0.7 });
    expect(detectFaces).toHaveBeenCalledWith(
      capture.uri,
      expect.objectContaining({
        classificationMode: 'all',
        performanceMode: 'fast',
        trackingEnabled: false,
      }),
    );
    expect(sample.photo.uri).toBe(capture.uri);
    expect(deleteImage).not.toHaveBeenCalled();
    await sample.photo.delete();
    await sample.photo.delete();
    expect(deleteImage).toHaveBeenCalledTimes(1);
    expect(deleteImage).toHaveBeenCalledWith(capture.uri);
  });

  test('rejects an overlapping request while the first capture is pending', async () => {
    let resolveCapture: ((value: typeof capture) => void) | undefined;
    const pendingCapture = new Promise<typeof capture>((resolve) => {
      resolveCapture = resolve;
    });
    const camera: LivenessStillCamera = {
      takePictureAsync: jest.fn(() => pendingCapture),
    };
    const source = createExpoCameraCaptureSource({
      deleteImage: async () => undefined,
      detectFaces: async () => [],
      getCamera: () => camera,
      platform: 'android',
    });

    const first = source.captureSample();
    await expectCaptureError(
      source.captureSample(),
      'capture_in_progress',
    );

    resolveCapture?.(capture);
    const firstSample = await first;
    expect(firstSample.observation).toMatchObject({ faceCount: 0 });
    await firstSample.photo.delete();
  });

  test('deletes the temporary image when face detection fails', async () => {
    const deleteImage = jest.fn(async () => undefined);
    const source = createExpoCameraCaptureSource({
      deleteImage,
      detectFaces: async () => {
        throw new Error('native detector failed');
      },
      getCamera: () => ({ takePictureAsync: async () => capture }),
      platform: 'android',
    });

    await expectCaptureError(source.captureSample(), 'detection_failed');
    expect(deleteImage).toHaveBeenCalledWith(capture.uri);
  });

  test('returns a typed capture failure without attempting cleanup when capture fails', async () => {
    const deleteImage = jest.fn(async () => undefined);
    const source = createExpoCameraCaptureSource({
      deleteImage,
      getCamera: () => ({
        takePictureAsync: async () => {
          throw new Error('camera failed');
        },
      }),
      platform: 'android',
    });

    await expectCaptureError(source.captureSample(), 'capture_failed');
    expect(deleteImage).not.toHaveBeenCalled();
  });

  test('reports temporary-file cleanup failures in typed form', async () => {
    const source = createExpoCameraCaptureSource({
      deleteImage: async () => {
        throw new Error('delete failed');
      },
      detectFaces: async () => [],
      getCamera: () => ({ takePictureAsync: async () => capture }),
      platform: 'android',
    });

    const sample = await source.captureSample();
    await expectCaptureError(sample.photo.delete(), 'cleanup_failed');
  });

  test('rejects unsupported platforms before accessing the camera', async () => {
    const getCamera = jest.fn<() => LivenessStillCamera | null>(() => null);
    const source = createExpoCameraCaptureSource({
      getCamera,
      platform: 'ios',
    });

    await expectCaptureError(source.captureSample(), 'unsupported_platform');
    expect(getCamera).not.toHaveBeenCalled();
  });

  test('reports a camera that is not ready without starting detection', async () => {
    const detectFaces = jest.fn(async () => []);
    const source = createExpoCameraCaptureSource({
      detectFaces,
      getCamera: () => null,
      platform: 'android',
    });

    await expectCaptureError(source.captureSample(), 'camera_unavailable');
    expect(detectFaces).not.toHaveBeenCalled();
  });
});
