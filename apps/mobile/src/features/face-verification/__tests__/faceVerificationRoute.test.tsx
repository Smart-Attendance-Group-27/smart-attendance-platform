import {
  beforeEach,
  describe,
  expect,
  jest,
  test,
} from '@jest/globals';
import { fireEvent, render } from '@testing-library/react-native';

import FaceVerificationRoute from '../../../app/(student)/attendance/[sessionId]/face-verification';

const mockPush = jest.fn();
let mockSearchParams: {
  sessionId?: string | string[];
};

jest.mock('expo-router', () => ({
  useLocalSearchParams: () => mockSearchParams,
  useRouter: () => ({
    push: mockPush,
  }),
}));

describe('FaceVerificationRoute', () => {
  beforeEach(() => {
    mockPush.mockClear();
    mockSearchParams = {
      sessionId: 'attendance-session-active',
    };
  });

  test('opens QR scanner with the normalized session ID after mock face verification', async () => {
    mockSearchParams = {
      sessionId: [' attendance-session-active ', 'ignored-session'],
    };
    const { getByRole } = await render(<FaceVerificationRoute />);

    await fireEvent.press(
      getByRole('button', {
        name: 'Continue to QR scanner',
      }),
    );

    expect(mockPush).toHaveBeenCalledTimes(1);
    expect(mockPush).toHaveBeenCalledWith(
      '/(student)/attendance/attendance-session-active/qr-scanner',
    );
  });

  test('keeps the friendly fallback for a missing session ID', async () => {
    mockSearchParams = {};
    const { getByText, queryByRole } = await render(
      <FaceVerificationRoute />,
    );

    expect(
      getByText(
        /We could not open this attendance step because the session link is incomplete/,
      ),
    ).toBeTruthy();
    expect(
      queryByRole('button', {
        name: 'Continue to QR scanner',
      }),
    ).toBeNull();
    expect(mockPush).not.toHaveBeenCalled();
  });
});
