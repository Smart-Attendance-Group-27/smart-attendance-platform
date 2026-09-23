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
const mockReplace = jest.fn();
let mockFaceVerificationLivenessMode: 'required' | 'off' | undefined;
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
    replace: mockReplace,
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
      livenessMode,
      onFaceVerified,
      sessionId,
    }: {
      livenessMode?: 'required' | 'off';
      onFaceVerified: (sessionId: string) => void;
      sessionId: string;
    }) => {
      mockFaceVerificationLivenessMode = livenessMode;

      return (
        <Pressable
          accessibilityLabel="Continue after face verification"
          accessibilityRole="button"
          onPress={() => onFaceVerified(sessionId)}
        >
          <Text>Continue</Text>
        </Pressable>
      );
    },
  };
});

describe('FaceVerificationRoute', () => {
  beforeEach(() => {
    mockPush.mockClear();
    mockReplace.mockClear();
    mockFaceVerificationLivenessMode = undefined;
    mockSearchParams = {
      sessionId: 'attendance-session-active',
    };
    mockAuthSession = {
      status: 'authenticated',
      userId: 'student-1',
      accessToken: 'test-access-token',
    };
  });

  test('uses the required liveness default for normal attendance', async () => {
    await render(<FaceVerificationRoute />);

    expect(mockFaceVerificationLivenessMode).toBeUndefined();
    expect(mockFaceVerificationLivenessMode).not.toBe('off');
  });

  test('opens Progress rather than QR after face verification', async () => {
    mockSearchParams = {
      sessionId: [' attendance-session-active ', 'ignored-session'],
      requiresQr: '1',
    };
    const { getByRole } = await render(<FaceVerificationRoute />);

    await fireEvent.press(
      getByRole('button', {
        name: 'Continue after face verification',
      }),
    );

    expect(mockReplace).toHaveBeenCalledTimes(1);
    expect(mockReplace).toHaveBeenCalledWith({
      pathname: '/(student)/attendance/[sessionId]/progress',
      params: {
        sessionId: 'attendance-session-active',
      },
    });
    expect(mockPush).not.toHaveBeenCalled();
  });

  test('uses Progress for sessions without QR too', async () => {
    mockSearchParams = {
      sessionId: 'attendance-session-active',
      requiresQr: '0',
    };
    const { getByRole } = await render(<FaceVerificationRoute />);

    await fireEvent.press(
      getByRole('button', {
        name: 'Continue after face verification',
      }),
    );

    expect(mockReplace).toHaveBeenCalledTimes(1);
    expect(mockReplace).toHaveBeenCalledWith({
      pathname: '/(student)/attendance/[sessionId]/progress',
      params: {
        sessionId: 'attendance-session-active',
      },
    });
    expect(mockPush).not.toHaveBeenCalled();
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
        name: 'Continue after face verification',
      }),
    ).toBeNull();
    expect(mockPush).not.toHaveBeenCalled();
  });
});
