import FaceDetection, {
  type Face,
  type FaceDetectionOptions,
} from '@react-native-ml-kit/face-detection';
import type { CameraType } from 'expo-camera';
import * as FileSystem from 'expo-file-system/legacy';
import { Platform } from 'react-native';

import { normalizeMlKitFaceObservation } from './mlKitObservation';
import type { NormalizedFaceObservation } from './livenessTypes';

export const LIVENESS_CAMERA_FACING: CameraType = 'front';

const CAPTURE_OPTIONS = { quality: 0.7 } as const;

const DETECTOR_OPTIONS: FaceDetectionOptions = {
  performanceMode: 'fast',
  landmarkMode: 'all',
  contourMode: 'none',
  classificationMode: 'all',
  minFaceSize: 0.1,
  trackingEnabled: false,
};

export type LivenessCaptureSourceErrorCode =
  | 'unsupported_platform'
  | 'camera_unavailable'
  | 'capture_in_progress'
  | 'capture_failed'
  | 'detection_failed'
  | 'invalid_capture'
  | 'cleanup_failed';

export class LivenessCaptureSourceError extends Error {
  readonly code: LivenessCaptureSourceErrorCode;
  readonly causeValue: unknown;

  constructor(
    code: LivenessCaptureSourceErrorCode,
    message: string,
    causeValue?: unknown,
  ) {
    super(message);
    this.name = 'LivenessCaptureSourceError';
    this.code = code;
    this.causeValue = causeValue;
  }
}

export type LivenessStillCamera = {
  takePictureAsync(options: typeof CAPTURE_OPTIONS): Promise<{
    readonly height: number;
    readonly uri: string;
    readonly width: number;
  }>;
};

export type LivenessCapturedPhoto = {
  readonly uri: string;
  delete(): Promise<void>;
};

export type LivenessCaptureSample = {
  readonly observation: NormalizedFaceObservation;
  readonly photo: LivenessCapturedPhoto;
};

type CaptureSourceDependencies = {
  readonly deleteImage?: (uri: string) => Promise<void>;
  readonly detectFaces?: (
    uri: string,
    options: FaceDetectionOptions,
  ) => Promise<readonly Face[]>;
  readonly getCamera: () => LivenessStillCamera | null;
  readonly now?: () => number;
  readonly platform?: string;
};

export type ExpoCameraCaptureSource = {
  captureSample(): Promise<LivenessCaptureSample>;
};

export function createExpoCameraCaptureSource({
  deleteImage = deleteTemporaryImage,
  detectFaces = FaceDetection.detect,
  getCamera,
  now = Date.now,
  platform = Platform.OS,
}: CaptureSourceDependencies): ExpoCameraCaptureSource {
  let processing = false;

  return {
    async captureSample(): Promise<LivenessCaptureSample> {
      if (platform !== 'android') {
        throw new LivenessCaptureSourceError(
          'unsupported_platform',
          'Liveness capture is currently supported only on Android.',
        );
      }

      if (processing) {
        throw new LivenessCaptureSourceError(
          'capture_in_progress',
          'A liveness capture is already being processed.',
        );
      }

      const camera = getCamera();
      if (!camera) {
        throw new LivenessCaptureSourceError(
          'camera_unavailable',
          'The front camera is not ready.',
        );
      }

      processing = true;
      let imageUri: string | null = null;
      let observation: NormalizedFaceObservation | null = null;
      let failure: LivenessCaptureSourceError | null = null;

      try {
        let capture;
        try {
          capture = await camera.takePictureAsync(CAPTURE_OPTIONS);
        } catch (error) {
          throw new LivenessCaptureSourceError(
            'capture_failed',
            'The liveness image could not be captured.',
            error,
          );
        }

        if (
          !capture ||
          typeof capture.uri !== 'string' ||
          capture.uri.length === 0
        ) {
          throw new LivenessCaptureSourceError(
            'invalid_capture',
            'The camera returned an invalid liveness image.',
          );
        }

        imageUri = capture.uri;
        const timestampMs = now();
        let faces: readonly Face[];

        try {
          faces = await detectFaces(imageUri, DETECTOR_OPTIONS);
        } catch (error) {
          throw new LivenessCaptureSourceError(
            'detection_failed',
            'Local face detection could not process the liveness image.',
            error,
          );
        }

        try {
          observation = normalizeMlKitFaceObservation({
            faces,
            imageHeight: capture.height,
            imageWidth: capture.width,
            timestampMs,
          });
        } catch (error) {
          throw new LivenessCaptureSourceError(
            'invalid_capture',
            'The camera returned invalid liveness image dimensions.',
            error,
          );
        }
      } catch (error) {
        failure = error instanceof LivenessCaptureSourceError
          ? error
          : new LivenessCaptureSourceError(
            'capture_failed',
            'The liveness capture could not be processed.',
            error,
          );
      } finally {
        if (imageUri && (!observation || failure)) {
          try {
            await deleteImage(imageUri);
          } catch (error) {
            failure ??= new LivenessCaptureSourceError(
              'cleanup_failed',
              'The temporary liveness image could not be deleted.',
              error,
            );
          }
        }
        processing = false;
      }

      if (failure) throw failure;
      if (!observation || !imageUri) {
        throw new LivenessCaptureSourceError(
          'capture_failed',
          'The liveness capture produced no observation.',
        );
      }

      const retainedImageUri = imageUri;
      let deleted = false;
      return {
        observation,
        photo: {
          uri: retainedImageUri,
          async delete() {
            if (deleted) return;
            try {
              await deleteImage(retainedImageUri);
              deleted = true;
            } catch (error) {
              throw new LivenessCaptureSourceError(
                'cleanup_failed',
                'The temporary liveness image could not be deleted.',
                error,
              );
            }
          },
        },
      };
    },
  };
}

async function deleteTemporaryImage(uri: string): Promise<void> {
  await FileSystem.deleteAsync(uri, { idempotent: true });
}
