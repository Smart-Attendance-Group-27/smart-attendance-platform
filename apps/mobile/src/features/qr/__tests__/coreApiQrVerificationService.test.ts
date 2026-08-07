import {
  afterEach,
  describe,
  expect,
  jest,
  test,
} from '@jest/globals';

import { CoreApiQrVerificationService } from '../services/coreApiQrVerificationService';

describe('CoreApiQrVerificationService', () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('posts qrValue to the backend verification endpoint', async () => {
    const fetchMock = jest.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({
        qrSessionId: 'qr-session-1',
        status: 'accepted',
        verifiedAt: '2026-08-07T10:30:00Z',
      }),
    } as Response);
    const service = new CoreApiQrVerificationService();

    const result = await service.verifyQrSession({
      qrSessionId: 'qr-session-1',
      qrValue: 'raw-secret-qr-value',
    });

    expect(result).toEqual({
      qrSessionId: 'qr-session-1',
      status: 'accepted',
      verifiedAt: '2026-08-07T10:30:00Z',
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/qr-sessions/qr-session-1/verify'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          qrValue: 'raw-secret-qr-value',
        }),
      }),
    );
  });

  test('rejects unrecognized backend responses', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({
        qrSessionId: 'qr-session-1',
        status: 'surprising',
        verifiedAt: '2026-08-07T10:30:00Z',
      }),
    } as Response);
    const service = new CoreApiQrVerificationService();

    await expect(
      service.verifyQrSession({
        qrSessionId: 'qr-session-1',
        qrValue: 'raw-secret-qr-value',
      }),
    ).rejects.toThrow('QR verification response was not recognized.');
  });
});
