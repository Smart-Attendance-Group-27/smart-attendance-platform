import type {
  QrVerificationRequest,
  QrVerificationResult,
} from '../types/qrVerification';

export interface QrVerificationService {
  verifyQrSession(
    request: QrVerificationRequest,
  ): Promise<QrVerificationResult>;
}
