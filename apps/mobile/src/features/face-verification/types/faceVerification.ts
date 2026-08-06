export type FaceCaptureInput = {
  uri: string;
};

export type FaceVerificationRequest = {
  sessionId: string;
  capture: FaceCaptureInput;
};

export type FaceVerificationResult =
  | { status: 'success' }
  | { status: 'face_not_detected' }
  | { status: 'multiple_faces' }
  | { status: 'liveness_failure' }
  | { status: 'verification_failure' };
