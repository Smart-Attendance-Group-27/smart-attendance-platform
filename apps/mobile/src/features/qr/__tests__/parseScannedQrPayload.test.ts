import {
  describe,
  expect,
  test,
} from '@jest/globals';

import { parseScannedQrPayload } from '../utils/parseScannedQrPayload';

describe('parseScannedQrPayload', () => {
  test('returns plain scanned text as the qrValue', () => {
    expect(parseScannedQrPayload(' raw-qr-value ')).toEqual({
      qrValue: 'raw-qr-value',
    });
  });

  test('extracts qrSessionId and qrValue from JSON payloads', () => {
    expect(
      parseScannedQrPayload(
        JSON.stringify({
          qrSessionId: 'qr-session-1',
          qrValue: 'raw-qr-value',
        }),
      ),
    ).toEqual({
      qrSessionId: 'qr-session-1',
      qrValue: 'raw-qr-value',
    });
  });

  test('trims empty payloads to an empty qrValue', () => {
    expect(parseScannedQrPayload('   ')).toEqual({
      qrValue: '',
    });
  });
});
