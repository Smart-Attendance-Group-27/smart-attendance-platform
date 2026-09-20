import {
  beforeEach,
  describe,
  expect,
  jest,
  test,
} from '@jest/globals';
import { act, render } from '@testing-library/react-native';

import QrScannerRoute from '../../../app/(student)/attendance/[sessionId]/qr-scanner';
import { mockQrSessionId, resetMockQrStore } from '../__fixtures__/mockQrStore';
import { resetMockAttendanceStore } from '../../attendance/__fixtures__/mockAttendanceStore';

const mockBack = jest.fn();
const mockDismissTo = jest.fn();
let mockBarcodeHandler: ((result: { data: string }) => void) | undefined;
let mockParams: { sessionId?: string | string[]; qrSessionId?: string } = {
  sessionId: 'session-1',
};

jest.mock('expo-router', () => ({
  useLocalSearchParams: () => mockParams,
  useRouter: () => ({ back: mockBack, dismissTo: mockDismissTo }),
}));

jest.mock('expo-camera', () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { Text } = require('react-native');

  return {
    CameraView: ({ onBarcodeScanned }: { onBarcodeScanned?: (result: { data: string }) => void }) => {
      mockBarcodeHandler = onBarcodeScanned;
      return <Text>Camera preview</Text>;
    },
    useCameraPermissions: () => [{ granted: true }, jest.fn()],
  };
});

jest.mock('../../auth/context/AuthContext', () => ({
  useAuth: () => ({
    session: {
      status: 'authenticated',
      accessToken: 'header.payload.signature',
    },
  }),
}));

describe('QrScannerRoute', () => {
  beforeEach(() => {
    mockParams = { sessionId: 'session-1' };
    mockBack.mockClear();
    mockDismissTo.mockClear();
    resetMockAttendanceStore();
    resetMockQrStore();
  });

  test('passes the route session id into the scanner screen', async () => {
    const { getByText } = await render(<QrScannerRoute />);

    expect(getByText('Scan attendance QR')).toBeTruthy();
    expect(getByText('Camera preview')).toBeTruthy();
  });

  test('shows an incomplete link message when session id is missing', async () => {
    mockParams = {};

    const { getByText } = await render(<QrScannerRoute />);

    expect(
      getByText(
        /We could not open this attendance step because the session link is incomplete./,
      ),
    ).toBeTruthy();
  });

  test('returns to Progress after an accepted scan', async () => {
    process.env.EXPO_PUBLIC_API_MODE = 'mock';
    const sessionId = 'attendance-session-checked-in';
    const qrSessionId = mockQrSessionId(sessionId, 2);
    mockParams = { sessionId, qrSessionId };
    try {
      await render(<QrScannerRoute />);
      await act(async () => {
        mockBarcodeHandler?.({ data: `mock-qr-value-${qrSessionId}` });
      });
      expect(mockDismissTo).toHaveBeenCalledWith({
        pathname: '/(student)/attendance/[sessionId]/progress', params: { sessionId },
      });
    } finally {
      delete process.env.EXPO_PUBLIC_API_MODE;
    }
  });
});
