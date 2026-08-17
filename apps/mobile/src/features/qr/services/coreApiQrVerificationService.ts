import type { CoreApiClient } from '../../../services/api/coreApiClient';
import type {
  QrVerificationRequest,
  QrVerificationResult,
  QrVerificationStatus,
} from '../types/qrVerification';
import type { QrVerificationService } from './qrVerificationService';

type VerifyQrSessionResponse = {
  qrSessionId?: unknown;
  status?: unknown;
  verifiedAt?: unknown;
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
      throw new Error('QR verification request failed.');
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
    typeof value.verifiedAt === 'string' &&
    typeof value.status === 'string' &&
    qrVerificationStatuses.has(value.status as QrVerificationStatus)
  );
}
