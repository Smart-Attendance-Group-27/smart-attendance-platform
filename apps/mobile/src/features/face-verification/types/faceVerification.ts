export type FaceCaptureInput = {
  uri: string;
};

export type FaceVerificationRequest = {
  sessionId: string;
  capture: FaceCaptureInput;
};

export type FaceVerificationResult =
  | { status: 'success' }
  | { status: 'face_not_detected'; canRetry?: boolean }
  | { status: 'multiple_faces'; canRetry?: boolean }
  | { status: 'liveness_failure'; canRetry?: boolean }
  | { status: 'verification_failure'; canRetry?: boolean };
