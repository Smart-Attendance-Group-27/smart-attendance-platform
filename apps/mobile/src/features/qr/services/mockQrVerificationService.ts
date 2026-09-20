import { getMockQrProgress, passMockBatch } from '../__fixtures__/mockQrStore';
import { QrVerificationError } from './qrVerificationService';
import type { QrVerificationService } from './qrVerificationService';
import type { QrVerificationRequest, QrVerificationResult } from '../types/qrVerification';

export class MockQrVerificationService implements QrVerificationService {
  async verifyQrSession({ qrSessionId, qrValue }: QrVerificationRequest): Promise<QrVerificationResult> {
    const sessionId = qrSessionId.replace(/-qr-[1-3]$/, '');
    const progress = getMockQrProgress(sessionId);
    if (!progress || !progress.qrEnabled) throw new QrVerificationError('not-found');
    if (!progress.checkedInAt) throw new QrVerificationError('check-in-required');
    const batch = progress.batches.find((item) => item.qrSessionId === qrSessionId);
    if (!batch) throw new QrVerificationError('not-found');
    const alreadyPassed = batch.passed;
    const status = alreadyPassed ? 'accepted' : batch.deactivatedAt ? 'closed'
      : qrValue === `mock-qr-value-${qrSessionId}` ? 'accepted' : 'invalid';
    if (status === 'accepted' && batch.required) passMockBatch(qrSessionId);
    return {
      qrSessionId, status, verifiedAt: new Date().toISOString(),
      batchPassed: status === 'accepted' || batch.passed,
      alreadyPassed: status === 'accepted' && alreadyPassed,
      requiredForStudent: batch.required,
    };
  }
}
