import {
  afterEach,
  beforeEach,
  describe,
  expect,
  jest,
  test,
} from '@jest/globals';

import { CoreApiClient } from '../../../services/api/coreApiClient';
import { CoreApiQrVerificationService } from '../services/coreApiQrVerificationService';

const accessToken = 'header.payload.signature';

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

function buildServiceWithToken(token: string | undefined) {
  return new CoreApiQrVerificationService(
    new CoreApiClient({
      baseUrl: 'http://10.0.2.2:8000',
      getAccessToken: () => token,
    }),
  );
}

function buildService() {
  return buildServiceWithToken(accessToken);
}

describe('CoreApiQrVerificationService', () => {
  beforeEach(() => {
    jest.spyOn(console, 'warn').mockImplementation(() => undefined);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('posts qrValue with a bearer token to the backend verification endpoint', async () => {
    const fetchMock = jest.spyOn(global, 'fetch').mockResolvedValue(
      jsonResponse(200, {
        qrSessionId: 'qr-session-1',
        status: 'accepted',
        verifiedAt: '2026-08-07T10:30:00Z',
      }),
    );

    const result = await buildService().verifyQrSession({
      qrSessionId: 'qr-session-1',
      qrValue: 'raw-secret-qr-value',
    });

    expect(result).toEqual({
      qrSessionId: 'qr-session-1',
      status: 'accepted',
      verifiedAt: '2026-08-07T10:30:00Z',
    });
    expect(fetchMock).toHaveBeenCalledWith(
      'http://10.0.2.2:8000/api/v1/qr-sessions/qr-session-1/verify',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        }),
        body: JSON.stringify({
          qrValue: 'raw-secret-qr-value',
        }),
      }),
    );
  });

  test('rejects unrecognized backend responses', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(
      jsonResponse(200, {
        qrSessionId: 'qr-session-1',
        status: 'surprising',
        verifiedAt: '2026-08-07T10:30:00Z',
      }),
    );

    await expect(
      buildService().verifyQrSession({
        qrSessionId: 'qr-session-1',
        qrValue: 'raw-secret-qr-value',
      }),
    ).rejects.toThrow('QR verification response was not recognized.');
  });

  test('throws when the backend rejects the request', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(jsonResponse(403, {}));

    await expect(
      buildService().verifyQrSession({
        qrSessionId: 'qr-session-1',
        qrValue: 'raw-secret-qr-value',
      }),
    ).rejects.toThrow('QR verification request failed.');
  });

  test('does not call the backend without an access token', async () => {
    const fetchMock = jest.spyOn(global, 'fetch');

    await expect(
      buildServiceWithToken(undefined).verifyQrSession({
        qrSessionId: 'qr-session-1',
        qrValue: 'raw-secret-qr-value',
      }),
    ).rejects.toThrow('QR verification request failed.');
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
