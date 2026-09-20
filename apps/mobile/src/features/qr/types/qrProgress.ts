import type { CoreApiFailureStatus } from '../../../services/api/coreApiClient';

export type QrBatchProgress = {
  qrSessionId: string;
  mode: string;
  activatedAt: string;
  deactivatedAt: string | null;
  expiresAt: string;
  voided: boolean;
  required: boolean;
  passed: boolean;
};

export type QrProgress = {
  sessionId: string;
  qrEnabled: boolean;
  checkedInAt: string | null;
  requiredCount: number;
  passedCount: number;
  activeBatch: Pick<QrBatchProgress,
    'qrSessionId' | 'mode' | 'activatedAt' | 'expiresAt' | 'required' | 'passed'> | null;
  batches: QrBatchProgress[];
};

export type QrProgressResult =
  | { status: 'loaded'; progress: QrProgress }
  | { status: CoreApiFailureStatus };
