import type { FaceVerificationService } from './faceVerificationService';
import type {
  FaceVerificationRequest,
  FaceVerificationResult,
} from '../types/faceVerification';

export type MockFaceVerificationServiceOptions = {
  readonly result: FaceVerificationResult;
  readonly delayMs?: number;
};

export class MockFaceVerificationService
  implements FaceVerificationService
{
  private readonly result: FaceVerificationResult;

  private readonly delayMs: number;

  constructor({
    result,
    delayMs = 0,
  }: MockFaceVerificationServiceOptions) {
    this.result = { ...result };
    this.delayMs = Number.isFinite(delayMs)
      ? Math.max(0, delayMs)
      : 0;
  }

  async verifyFace(
    _request: FaceVerificationRequest,
  ): Promise<FaceVerificationResult> {
    if (this.delayMs > 0) {
      await new Promise<void>((resolve) => {
        setTimeout(resolve, this.delayMs);
      });
    }

    return { ...this.result };
  }
}
