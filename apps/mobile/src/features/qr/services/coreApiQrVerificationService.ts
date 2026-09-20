import type { CoreApiClient } from '../../../services/api/coreApiClient';
import type {
  QrVerificationRequest,
  QrVerificationResult,
  QrVerificationStatus,
} from '../types/qrVerification';
import type { QrVerificationService } from './qrVerificationService';
import { QrVerificationError } from './qrVerificationService';

type VerifyQrSessionResponse = {
  qrSessionId?: unknown;
  status?: unknown;
  verifiedAt?: unknown;
  batchPassed?: unknown;
  alreadyPassed?: unknown;
  requiredForStudent?: unknown;
};

const qrVerificationStatuses = new Set<QrVerificationStatus>([
  'accepted',
  'invalid',
  'expired',
  'closed',
]);

export class CoreApiQrVerificationService implements QrVerificationService {
  constructor(private readonly coreApiClient: CoreApiClient) {}

  async verifyQrSession({
    qrSessionId,
    qrValue,
  }: QrVerificationRequest): Promise<QrVerificationResult> {
    const result = await this.coreApiClient.post<VerifyQrSessionResponse>(
      `/api/v1/qr-sessions/${encodeURIComponent(qrSessionId)}/verify`,
      { qrValue },
    );

    if (result.status !== 'ok') {
      throw new QrVerificationError(
        result.status === 'conflict' && result.errorCode === 'CHECK_IN_REQUIRED'
          ? 'check-in-required'
          : result.status === 'not-found' ? 'not-found'
            : result.status === 'forbidden' ? 'forbidden' : 'unavailable',
      );
    }

    if (!isQrVerificationResponse(result.data)) {
      throw new Error('QR verification response was not recognized.');
    }

    return result.data;
  }
}

function isQrVerificationResponse(
  value: VerifyQrSessionResponse,
): value is QrVerificationResult {
  return (
    typeof value.qrSessionId === 'string' &&
    typeof value.verifiedAt === 'string' && Number.isFinite(Date.parse(value.verifiedAt)) &&
    typeof value.batchPassed === 'boolean' &&
    typeof value.alreadyPassed === 'boolean' &&
    typeof value.requiredForStudent === 'boolean' &&
    typeof value.status === 'string' &&
    qrVerificationStatuses.has(value.status as QrVerificationStatus)
  );
}
