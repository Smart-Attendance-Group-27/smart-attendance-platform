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
  requiresQr?: string | string[];
};
let mockAuthSession:
  | {
      status: 'authenticated';
      userId: string;
      accessToken: string;
    }
  | { status: 'unauthenticated' };

jest.mock('expo-router', () => ({
  useLocalSearchParams: () => mockSearchParams,
  useRouter: () => ({
    push: mockPush,
  }),
}));

jest.mock('../../auth/context/AuthContext', () => ({
  useAuth: () => ({ session: mockAuthSession }),
}));

jest.mock('../screens/FaceVerificationScreen', () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { Pressable, Text } = require('react-native');

  return {
    FaceVerificationScreen: ({
      onFaceVerified,
      sessionId,
    }: {
      onFaceVerified: (sessionId: string) => void;
      sessionId: string;
    }) => (
      <Pressable
        accessibilityLabel="Continue to QR scanner"
        accessibilityRole="button"
        onPress={() => onFaceVerified(sessionId)}
      >
        <Text>Continue</Text>
      </Pressable>
    ),
  };
});

describe('FaceVerificationRoute', () => {
  beforeEach(() => {
    mockPush.mockClear();
    mockSearchParams = {
      sessionId: 'attendance-session-active',
    };
    mockAuthSession = {
      status: 'authenticated',
      userId: 'student-1',
      accessToken: 'test-access-token',
    };
  });

  test('opens QR scanner with the normalized session ID after face verification when the session requires QR', async () => {
    mockSearchParams = {
      sessionId: [' attendance-session-active ', 'ignored-session'],
      requiresQr: '1',
    };
    const { getByRole } = await render(<FaceVerificationRoute />);

    await fireEvent.press(
      getByRole('button', {
        name: 'Continue to QR scanner',
      }),
    );

    expect(mockPush).toHaveBeenCalledTimes(1);
    expect(mockPush).toHaveBeenCalledWith({
      pathname:
        '/(student)/attendance/[sessionId]/qr-scanner',
      params: {
        sessionId: 'attendance-session-active',
      },
    });
  });

  test('skips the QR scanner and goes straight to check-in success when the session does not require QR', async () => {
    mockSearchParams = {
      sessionId: 'attendance-session-active',
      requiresQr: '0',
    };
    const { getByRole } = await render(<FaceVerificationRoute />);

    await fireEvent.press(
      getByRole('button', {
        name: 'Continue to QR scanner',
      }),
    );

    expect(mockPush).toHaveBeenCalledTimes(1);
    expect(mockPush).toHaveBeenCalledWith({
      pathname:
        '/(student)/attendance/[sessionId]/check-in-success',
      params: {
        sessionId: 'attendance-session-active',
      },
    });
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
