import type {
  QrVerificationRequest,
  QrVerificationResult,
  QrVerificationStatus,
} from '../types/qrVerification';
import type { QrVerificationService } from './qrVerificationService';

const defaultCoreApiBaseUrl = 'http://10.0.2.2:8000';
const QR_VERIFICATION_TIMEOUT_MS = 10_000;

const coreApiBaseUrl =
  process.env.EXPO_PUBLIC_CORE_API_URL?.trim() || defaultCoreApiBaseUrl;

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
  async verifyQrSession({
    qrSessionId,
    qrValue,
  }: QrVerificationRequest): Promise<QrVerificationResult> {
    const abortController = new AbortController();
    const timeoutId = setTimeout(() => {
      abortController.abort();
    }, QR_VERIFICATION_TIMEOUT_MS);

    try {
      const response = await fetch(
        `${coreApiBaseUrl}/api/v1/qr-sessions/${encodeURIComponent(
          qrSessionId,
        )}/verify`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            qrValue,
          }),
          signal: abortController.signal,
        },
      );

      const responsePayload = (await response.json()) as VerifyQrSessionResponse;

      if (!response.ok) {
        throw new Error('QR verification request failed.');
      }

      if (!isQrVerificationResponse(responsePayload)) {
        throw new Error('QR verification response was not recognized.');
      }

      return responsePayload;
    } finally {
      clearTimeout(timeoutId);
    }
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
