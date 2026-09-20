import { getMockAttendance } from '../../attendance/__fixtures__/mockAttendanceStore';
import type { QrBatchProgress, QrProgress } from '../types/qrProgress';

const passedBatches = new Set<string>();
const activations = [
  '2026-07-20T10:01:00+05:30',
  '2026-07-20T10:06:00+05:30',
  '2026-07-20T10:11:00+05:30',
];

export function resetMockQrStore(): void {
  passedBatches.clear();
}

export function mockQrSessionId(sessionId: string, index: number): string {
  return `${sessionId}-qr-${index + 1}`;
}

export function getMockQrProgress(sessionId: string): QrProgress | null {
  const attendance = getMockAttendance(sessionId);
  if (!attendance) return null;
  const checkedInAt = attendance.initialCheckIn?.checkedInAt ?? null;
  const batches: QrBatchProgress[] = attendance.qrEnabled ? activations.map((activatedAt, index) => {
    const qrSessionId = mockQrSessionId(sessionId, index);
    const required = Boolean(checkedInAt && Date.parse(activatedAt) > Date.parse(checkedInAt));
    return {
      qrSessionId,
      mode: 'rotating',
      activatedAt,
      deactivatedAt: index < 2 ? activations[index + 1] : null,
      expiresAt: '2026-07-20T12:00:00+05:30',
      voided: false,
      required,
      passed: required && passedBatches.has(qrSessionId),
    };
  }) : [];
  const active = attendance.sessionState === 'active' ? batches.at(-1) : undefined;
  return {
    sessionId,
    qrEnabled: attendance.qrEnabled,
    checkedInAt,
    requiredCount: batches.filter((batch) => batch.required).length,
    passedCount: batches.filter((batch) => batch.required && batch.passed).length,
    activeBatch: active ? {
      qrSessionId: active.qrSessionId,
      mode: active.mode,
      activatedAt: active.activatedAt,
      expiresAt: active.expiresAt,
      required: active.required,
      passed: active.passed,
    } : null,
    batches,
  };
}

export function passMockBatch(qrSessionId: string): void {
  passedBatches.add(qrSessionId);
}
