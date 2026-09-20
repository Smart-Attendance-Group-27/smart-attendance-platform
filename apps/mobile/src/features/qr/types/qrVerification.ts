export type QrVerificationStatus =
  | 'accepted'
  | 'invalid'
  | 'expired'
  | 'closed';

export type QrVerificationRequest = {
  qrSessionId: string;
  qrValue: string;
};

export type QrVerificationResult = {
  qrSessionId: string;
  status: QrVerificationStatus;
  verifiedAt: string;
  batchPassed: boolean;
  alreadyPassed: boolean;
  requiredForStudent: boolean;
};

export type ScannedQrPayload = {
  qrSessionId?: string;
  qrValue: string;
};
