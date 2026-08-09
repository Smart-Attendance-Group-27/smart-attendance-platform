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
};

export type ScannedQrPayload = {
  qrSessionId?: string;
  qrValue: string;
};
