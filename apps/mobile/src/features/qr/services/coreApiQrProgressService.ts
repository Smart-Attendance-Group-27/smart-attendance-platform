import type { CoreApiClient } from '../../../services/api/coreApiClient';
import type { QrBatchProgress, QrProgress, QrProgressResult } from '../types/qrProgress';
import type { QrProgressService } from './qrProgressService';

const isRecord = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === 'object' && !Array.isArray(value);
const isDate = (value: unknown): value is string =>
  typeof value === 'string' && Number.isFinite(Date.parse(value));
const isNullableDate = (value: unknown): value is string | null =>
  value === null || isDate(value);
const isCount = (value: unknown): value is number =>
  typeof value === 'number' && Number.isInteger(value) && value >= 0;

function isBatch(value: unknown): value is QrBatchProgress {
  return isRecord(value) && typeof value.qrSessionId === 'string' &&
    typeof value.mode === 'string' && isDate(value.activatedAt) &&
    isNullableDate(value.deactivatedAt) && isDate(value.expiresAt) &&
    typeof value.voided === 'boolean' && typeof value.required === 'boolean' &&
    typeof value.passed === 'boolean';
}

export function parseQrProgress(value: unknown, sessionId: string): QrProgress | null {
  if (!isRecord(value) || value.sessionId !== sessionId ||
      typeof value.qrEnabled !== 'boolean' || !isNullableDate(value.checkedInAt) ||
      !isCount(value.requiredCount) || !isCount(value.passedCount) ||
      value.passedCount > value.requiredCount || !Array.isArray(value.batches) ||
      !value.batches.every(isBatch)) return null;
  const active = value.activeBatch;
  if (active !== null && (!isRecord(active) ||
      typeof active.qrSessionId !== 'string' || typeof active.mode !== 'string' ||
      !isDate(active.activatedAt) || !isDate(active.expiresAt) ||
      typeof active.required !== 'boolean' || typeof active.passed !== 'boolean')) return null;
  return value as QrProgress;
}

export class CoreApiQrProgressService implements QrProgressService {
  constructor(private readonly client: CoreApiClient) {}

  async getQrProgress(sessionId: string): Promise<QrProgressResult> {
    const result = await this.client.get<unknown>(
      `/api/v1/attendance-sessions/${encodeURIComponent(sessionId)}/qr-progress`,
    );
    if (result.status !== 'ok') return { status: result.status };
    const progress = parseQrProgress(result.data, sessionId);
    return progress ? { status: 'loaded', progress } : { status: 'server-error' };
  }
}
