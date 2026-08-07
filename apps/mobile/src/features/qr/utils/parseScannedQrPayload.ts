import type { ScannedQrPayload } from '../types/qrVerification';

export function parseScannedQrPayload(scannedValue: string): ScannedQrPayload {
  const trimmedValue = scannedValue.trim();

  if (!trimmedValue) {
    return {
      qrValue: '',
    };
  }

  try {
    const parsedValue = JSON.parse(trimmedValue) as unknown;

    if (
      parsedValue &&
      typeof parsedValue === 'object' &&
      'qrValue' in parsedValue &&
      typeof parsedValue.qrValue === 'string'
    ) {
      const qrSessionId =
        'qrSessionId' in parsedValue &&
        typeof parsedValue.qrSessionId === 'string'
          ? parsedValue.qrSessionId.trim()
          : undefined;

      return {
        qrSessionId: qrSessionId || undefined,
        qrValue: parsedValue.qrValue.trim(),
      };
    }
  } catch {
    // Plain raw QR values are supported for scanners that receive the
    // qrSessionId from route params instead of the QR payload.
  }

  return {
    qrValue: trimmedValue,
  };
}
