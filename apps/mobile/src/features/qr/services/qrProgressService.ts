import type { QrProgressResult } from '../types/qrProgress';

export interface QrProgressService {
  getQrProgress(sessionId: string): Promise<QrProgressResult>;
}
