import { getMockQrProgress } from '../__fixtures__/mockQrStore';
import type { QrProgressService } from './qrProgressService';

export class MockQrProgressService implements QrProgressService {
  async getQrProgress(sessionId: string) {
    const progress = getMockQrProgress(sessionId);
    return progress
      ? { status: 'loaded' as const, progress }
      : { status: 'not-found' as const };
  }
}
