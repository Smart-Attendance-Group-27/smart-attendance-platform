import type { Face } from '@react-native-ml-kit/face-detection';

import type { NormalizedFaceObservation } from './livenessTypes';

export type MlKitObservationInput = {
  readonly faces: readonly Face[];
  readonly imageWidth: number;
  readonly imageHeight: number;
  readonly timestampMs: number;
};

/**
 * Converts one still-image ML Kit result into the camera-independent input
 * consumed by the S2 liveness engine.
 *
 * Physical-device measurements show that ML Kit's front-camera rotationY is
 * positive when the user turns right and negative when the user turns left.
 * Normalize that raw value to the engine convention: positive is user-left
 * and negative is user-right.
 */
export function normalizeMlKitFaceObservation({
  faces,
  imageWidth,
  imageHeight,
  timestampMs,
}: MlKitObservationInput): NormalizedFaceObservation {
  assertPositiveDimension(imageWidth, 'width');
  assertPositiveDimension(imageHeight, 'height');

  const face = faces.length === 1 ? faces[0] : undefined;
  const observation: NormalizedFaceObservation = {
    timestampMs,
    faceCount: faces.length,
    yawDegrees: face === undefined ? null : -face.rotationY,
    leftEyeOpenProbability: face?.leftEyeOpenProbability ?? null,
    rightEyeOpenProbability: face?.rightEyeOpenProbability ?? null,
    faceAreaRatio: face
      ? (face.frame.width * face.frame.height) / (imageWidth * imageHeight)
      : 0,
  };

  return face?.trackingID === undefined
    ? observation
    : { ...observation, trackingId: face.trackingID };
}

function assertPositiveDimension(value: number, name: string): void {
  if (!Number.isFinite(value) || value <= 0) {
    throw new RangeError(`Image ${name} must be a positive finite number.`);
  }
}
