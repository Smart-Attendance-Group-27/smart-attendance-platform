import {
  beforeEach,
  describe,
  expect,
  jest,
  test,
} from '@jest/globals';
import {
  act,
  fireEvent,
  render,
  waitFor,
} from '@testing-library/react-native';

import { QrScannerScreen } from '../screens/QrScannerScreen';
import type { QrVerificationService } from '../services/qrVerificationService';

const mockRequestPermission = jest.fn();
let mockPermissionState: { granted: boolean } | null = { granted: true };
let mockBarcodeHandler:
  | ((result: { data: string }) => void)
  | undefined;

jest.mock('expo-camera', () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { Pressable, Text } = require('react-native');

  return {
    CameraView: ({
      onBarcodeScanned,
    }: {
      onBarcodeScanned?: (result: { data: string }) => void;
    }) => {
      mockBarcodeHandler = onBarcodeScanned;

      return (
        <Pressable
          accessibilityLabel="Camera preview"
          onPress={() => onBarcodeScanned?.({ data: 'decoded-qr-value' })}
        >
          <Text>Camera preview</Text>
        </Pressable>
      );
    },
    useCameraPermissions: () => [
      mockPermissionState,
      mockRequestPermission,
    ],
  };
});

describe('QrScannerScreen', () => {
  beforeEach(() => {
    mockRequestPermission.mockClear();
    mockPermissionState = { granted: true };
    mockBarcodeHandler = undefined;
  });

  test('verifies a scanned QR payload and shows the result without raw QR text', async () => {
    const verifyQrSession = jest.fn<Required<QrVerificationService>['verifyQrSession']>(
      async () => ({
        qrSessionId: 'qr-session-1',
        status: 'accepted',
        verifiedAt: '2026-08-07T10:30:00Z',
      }),
    );
    const onQrVerified = jest.fn();
    const { getByLabelText, queryByText, findByText } = await render(
      <QrScannerScreen
        onBack={jest.fn()}
        onQrVerified={onQrVerified}
        qrVerificationService={{ verifyQrSession }}
        sessionId="session-1"
      />,
    );

    await act(async () => {
      mockBarcodeHandler?.({
        data: JSON.stringify({
          qrSessionId: 'qr-session-1',
          qrValue: 'decoded-qr-value',
        }),
      });
    });

    await waitFor(() => {
      expect(verifyQrSession).toHaveBeenCalledWith({
        qrSessionId: 'qr-session-1',
        qrValue: 'decoded-qr-value',
      });
    });
    expect(onQrVerified).toHaveBeenCalledWith({
      qrSessionId: 'qr-session-1',
      status: 'accepted',
      verifiedAt: '2026-08-07T10:30:00Z',
    });
    expect(await findByText('QR verified')).toBeTruthy();
    expect(queryByText('decoded-qr-value')).toBeNull();
    expect(getByLabelText('Scan another QR code')).toBeTruthy();
  });

  test('ignores empty decoded QR values', async () => {
    const verifyQrSession = jest.fn<Required<QrVerificationService>['verifyQrSession']>();
    await render(
      <QrScannerScreen
        onBack={jest.fn()}
        qrVerificationService={{ verifyQrSession }}
        sessionId="session-1"
      />,
    );

    await act(async () => {
      mockBarcodeHandler?.({ data: '   ' });
    });

    expect(verifyQrSession).not.toHaveBeenCalled();
  });

  test('uses the route qrSessionId when scanning a plain raw QR value', async () => {
    const verifyQrSession = jest.fn<Required<QrVerificationService>['verifyQrSession']>(
      async () => ({
        qrSessionId: 'qr-session-from-route',
        status: 'invalid',
        verifiedAt: '2026-08-07T10:30:00Z',
      }),
    );
    const { findByText } = await render(
      <QrScannerScreen
        onBack={jest.fn()}
        qrSessionId="qr-session-from-route"
        qrVerificationService={{ verifyQrSession }}
        sessionId="session-1"
      />,
    );

    await act(async () => {
      mockBarcodeHandler?.({ data: 'plain-raw-qr-value' });
    });

    await waitFor(() => {
      expect(verifyQrSession).toHaveBeenCalledWith({
        qrSessionId: 'qr-session-from-route',
        qrValue: 'plain-raw-qr-value',
      });
    });
    expect(await findByText('Invalid QR code')).toBeTruthy();
  });

  test('shows a friendly error when QR session id is unavailable', async () => {
    const verifyQrSession = jest.fn<Required<QrVerificationService>['verifyQrSession']>();
    const { findByText } = await render(
      <QrScannerScreen
        onBack={jest.fn()}
        qrVerificationService={{ verifyQrSession }}
        sessionId="session-1"
      />,
    );

    await act(async () => {
      mockBarcodeHandler?.({ data: 'plain-raw-qr-value' });
    });

    expect(await findByText('QR session ID missing')).toBeTruthy();
    expect(verifyQrSession).not.toHaveBeenCalled();
  });

  test('requests camera permission when access has not been granted', async () => {
    mockPermissionState = { granted: false };
    const { getByLabelText, getByText } = await render(
      <QrScannerScreen
        onBack={jest.fn()}
        qrVerificationService={{
          verifyQrSession: jest.fn<Required<QrVerificationService>['verifyQrSession']>(),
        }}
        sessionId="session-1"
      />,
    );

    expect(getByText('Camera permission required')).toBeTruthy();

    fireEvent.press(getByLabelText('Allow camera access'));

    expect(mockRequestPermission).toHaveBeenCalledTimes(1);
  });
});
