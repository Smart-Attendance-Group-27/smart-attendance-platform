import {
  beforeEach,
  describe,
  expect,
  jest,
  test,
} from '@jest/globals';
import { render } from '@testing-library/react-native';

import QrScannerRoute from '../../../app/(student)/attendance/[sessionId]/qr-scanner';

const mockBack = jest.fn();
let mockParams: { sessionId?: string | string[] } = {
  sessionId: 'session-1',
};

jest.mock('expo-router', () => ({
  useLocalSearchParams: () => mockParams,
  useRouter: () => ({ back: mockBack }),
}));

jest.mock('expo-camera', () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { Text } = require('react-native');

  return {
    CameraView: () => <Text>Camera preview</Text>,
    useCameraPermissions: () => [{ granted: true }, jest.fn()],
  };
});

describe('QrScannerRoute', () => {
  beforeEach(() => {
    mockParams = { sessionId: 'session-1' };
    mockBack.mockClear();
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
});
