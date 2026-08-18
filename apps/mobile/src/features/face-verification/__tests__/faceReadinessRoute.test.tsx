import { beforeEach, describe, expect, jest, test } from '@jest/globals';
import { fireEvent, render } from '@testing-library/react-native';

import FaceReadinessRoute from '../../../app/(student)/face-readiness';

const mockBack = jest.fn();

jest.mock('expo-router', () => ({
  useRouter: () => ({ back: mockBack }),
}));

jest.mock('../../auth/context/AuthContext', () => ({
  useAuth: () => ({
    session: {
      status: 'authenticated',
      accessToken: 'header.payload.signature',
    },
  }),
}));

jest.mock('../screens/FaceVerificationScreen', () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { Pressable, Text, View } = require('react-native');

  return {
    FaceVerificationScreen: ({
      mode,
      onBack,
      onFaceVerified,
    }: {
      mode: string;
      onBack: () => void;
      onFaceVerified: () => void;
    }) => (
      <View>
        <Text>{mode}</Text>
        <Pressable
          accessibilityLabel="Go back"
          accessibilityRole="button"
          onPress={onBack}
        />
        <Pressable
          accessibilityLabel="Complete readiness verification"
          accessibilityRole="button"
          onPress={onFaceVerified}
        />
      </View>
    ),
  };
});

describe('FaceReadinessRoute', () => {
  beforeEach(() => {
    mockBack.mockClear();
  });

  test('opens the shared camera in readiness mode', async () => {
    const screen = await render(<FaceReadinessRoute />);

    expect(screen.getByText('readiness')).toBeTruthy();

    await fireEvent.press(
      screen.getByRole('button', {
        name: 'Complete readiness verification',
      }),
    );

    expect(mockBack).toHaveBeenCalledTimes(1);
  });

  test('returns to the dashboard from the back action', async () => {
    const screen = await render(<FaceReadinessRoute />);

    await fireEvent.press(
      screen.getByRole('button', { name: 'Go back' }),
    );

    expect(mockBack).toHaveBeenCalledTimes(1);
  });
});
