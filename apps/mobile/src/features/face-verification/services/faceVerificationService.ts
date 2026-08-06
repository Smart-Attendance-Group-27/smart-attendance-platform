import type {
  FaceVerificationRequest,
  FaceVerificationResult,
} from '../types/faceVerification';

export interface FaceVerificationService {
  verifyFace(
    request: FaceVerificationRequest,
  ): Promise<FaceVerificationResult>;
}
