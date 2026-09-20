import type {
  QrVerificationRequest,
  QrVerificationResult,
} from '../types/qrVerification';

export interface QrVerificationService {
  verifyQrSession(
    request: QrVerificationRequest,
  ): Promise<QrVerificationResult>;
}

export class QrVerificationError extends Error {
  constructor(public readonly reason: 'check-in-required' | 'not-found' | 'forbidden' | 'unavailable') {
    super(reason);
  }
}
