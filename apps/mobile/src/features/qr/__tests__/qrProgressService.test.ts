import { afterEach, beforeEach, describe, expect, jest, test } from '@jest/globals';

import { CoreApiClient } from '../../../services/api/coreApiClient';
import { resetMockAttendanceStore } from '../../attendance/__fixtures__/mockAttendanceStore';
import { mockQrSessionId, resetMockQrStore } from '../__fixtures__/mockQrStore';
import { CoreApiQrProgressService } from '../services/coreApiQrProgressService';
import { MockQrProgressService } from '../services/mockQrProgressService';
import { MockQrVerificationService } from '../services/mockQrVerificationService';

const sessionId = 'attendance-session-checked-in';

describe('QR progress contract', () => {
  beforeEach(() => {
    resetMockAttendanceStore();
    resetMockQrStore();
    jest.spyOn(console, 'warn').mockImplementation(() => undefined);
  });
  afterEach(() => { jest.restoreAllMocks(); });

  test('tracks required batches after check-in and counts a duplicate once', async () => {
    const progressService = new MockQrProgressService();
    const verificationService = new MockQrVerificationService();
    const qrSessionId = mockQrSessionId(sessionId, 2);
    const request = { qrSessionId, qrValue: `mock-qr-value-${qrSessionId}` };
    expect(await progressService.getQrProgress(sessionId)).toMatchObject({
      status: 'loaded', progress: { requiredCount: 2, passedCount: 0,
        activeBatch: { qrSessionId, required: true, passed: false } },
    });

    expect(await verificationService.verifyQrSession(request)).toMatchObject({
      status: 'accepted', batchPassed: true, alreadyPassed: false, requiredForStudent: true,
    });
    expect(await verificationService.verifyQrSession(request)).toMatchObject({
      status: 'accepted', batchPassed: true, alreadyPassed: true, requiredForStudent: true,
    });
    expect(await progressService.getQrProgress(sessionId)).toMatchObject({
      status: 'loaded', progress: { requiredCount: 2, passedCount: 1,
        activeBatch: { passed: true } },
    });
  });

  test('requires initial check-in and marks earlier batches as not required', async () => {
    const verificationService = new MockQrVerificationService();
    const beforeCheckInId = mockQrSessionId('attendance-session-active', 2);
    await expect(verificationService.verifyQrSession({
      qrSessionId: beforeCheckInId, qrValue: `mock-qr-value-${beforeCheckInId}`,
    })).rejects.toThrow('check-in-required');
    expect(await new MockQrProgressService().getQrProgress('attendance-session-late'))
      .toMatchObject({ status: 'loaded', progress: { requiredCount: 0, passedCount: 0,
        activeBatch: { required: false } } });
  });

  test('reads C08 from the authenticated backend and rejects malformed counts', async () => {
    const client = new CoreApiClient({ baseUrl: 'https://api.example.test', getAccessToken: () => 'token' });
    const service = new CoreApiQrProgressService(client);
    const fetchMock = jest.spyOn(global, 'fetch').mockResolvedValue({
      ok: true, status: 200, json: async () => ({
        sessionId, qrEnabled: true, checkedInAt: '2026-07-20T10:02:00+05:30',
        requiredCount: 1, passedCount: 0, activeBatch: null, batches: [],
      }),
    } as Response);
    expect(await service.getQrProgress(sessionId)).toMatchObject({
      status: 'loaded', progress: { requiredCount: 1 },
    });
    expect(fetchMock).toHaveBeenCalledWith(
      `https://api.example.test/api/v1/attendance-sessions/${sessionId}/qr-progress`,
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: 'Bearer token' }) }),
    );
    fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => ({
      sessionId, qrEnabled: true, checkedInAt: null,
      requiredCount: 0, passedCount: 1, activeBatch: null, batches: [],
    }) } as Response);
    expect(await service.getQrProgress(sessionId)).toEqual({ status: 'server-error' });
  });
});
