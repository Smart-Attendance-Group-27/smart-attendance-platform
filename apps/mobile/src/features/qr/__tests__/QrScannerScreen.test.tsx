import {
  beforeEach,
  describe,
  expect,
  jest,
  test,
} from '@jest/globals';
import { fireEvent, render } from '@testing-library/react-native';

import { QrScannerScreen } from '../screens/QrScannerScreen';

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

  test('shows camera preview and returns the decoded qrValue', async () => {
    const onQrScanned = jest.fn();
    const { findByText, getByLabelText } = await render(
      <QrScannerScreen
        onBack={jest.fn()}
        onQrScanned={onQrScanned}
        sessionId="session-1"
      />,
    );

    fireEvent.press(getByLabelText('Camera preview'));

    expect(onQrScanned).toHaveBeenCalledWith({
      sessionId: 'session-1',
      qrValue: 'decoded-qr-value',
    });
    expect(await findByText('QR captured successfully')).toBeTruthy();
    expect(await findByText('decoded-qr-value')).toBeTruthy();
  });

  test('ignores empty decoded QR values', async () => {
    const onQrScanned = jest.fn();
    await render(
      <QrScannerScreen
        onBack={jest.fn()}
        onQrScanned={onQrScanned}
        sessionId="session-1"
      />,
    );

    mockBarcodeHandler?.({ data: '   ' });

    expect(onQrScanned).not.toHaveBeenCalled();
  });

  test('requests camera permission when access has not been granted', async () => {
    mockPermissionState = { granted: false };
    const { getByLabelText, getByText } = await render(
      <QrScannerScreen onBack={jest.fn()} sessionId="session-1" />,
    );

    expect(getByText('Camera permission required')).toBeTruthy();

    fireEvent.press(getByLabelText('Allow camera access'));

    expect(mockRequestPermission).toHaveBeenCalledTimes(1);
  });
});
