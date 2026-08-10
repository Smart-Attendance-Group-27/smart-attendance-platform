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
        accessibilityLabel="Continue to check-in result"
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
  });

  test('opens check-in success with the normalized session ID after face verification', async () => {
    mockSearchParams = {
      sessionId: [' attendance-session-active ', 'ignored-session'],
    };
    const { getByRole } = await render(<FaceVerificationRoute />);

    await fireEvent.press(
      getByRole('button', {
        name: 'Continue to check-in result',
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
        name: 'Continue to check-in result',
      }),
    ).toBeNull();
    expect(mockPush).not.toHaveBeenCalled();
  });
});
