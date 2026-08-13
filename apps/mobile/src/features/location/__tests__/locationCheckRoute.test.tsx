import {
  beforeEach,
  describe,
  expect,
  jest,
  test,
} from '@jest/globals';
import { fireEvent, render } from '@testing-library/react-native';

import LocationCheckRoute from '../../../app/(student)/attendance/[sessionId]/location-check';

const mockBack = jest.fn();
const mockPush = jest.fn();
let mockSearchParams: {
  sessionId?: string | string[];
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
    back: mockBack,
    push: mockPush,
  }),
}));

jest.mock('../../auth/context/AuthContext', () => ({
  useAuth: () => ({ session: mockAuthSession }),
}));

jest.mock('../services/liveLocationService', () => ({
  LiveLocationService: class {
    async validateLocation() {
      return { status: 'inside_geofence' as const };
    }
  },
}));

describe('LocationCheckRoute', () => {
  beforeEach(() => {
    mockBack.mockClear();
    mockPush.mockClear();
    mockSearchParams = {
      sessionId: 'attendance-session-active',
    };
    mockAuthSession = {
      status: 'authenticated',
      userId: 'student-user-id',
      accessToken: 'header.payload.signature',
    };
  });

  test('opens face introduction with the normalized session ID only after successful validation', async () => {
    mockSearchParams = {
      sessionId: [' attendance-session-active ', 'ignored-session'],
    };
    const { findByRole, getByRole } = await render(
      <LocationCheckRoute />,
    );

    expect(mockPush).not.toHaveBeenCalled();

    await fireEvent.press(
      getByRole('button', {
        name: 'Allow location access and check classroom location',
      }),
    );

    expect(mockPush).not.toHaveBeenCalled();

    await fireEvent.press(
      await findByRole('button', {
        name: 'Continue to face verification',
      }),
    );

    expect(mockPush).toHaveBeenCalledTimes(1);
    expect(mockPush).toHaveBeenCalledWith({
      pathname:
        '/(student)/attendance/[sessionId]/face-introduction',
      params: {
        sessionId: 'attendance-session-active',
      },
    });
  });

  test('uses router back for the screen back action', async () => {
    const { getByRole } = await render(<LocationCheckRoute />);

    await fireEvent.press(
      getByRole('button', {
        name: 'Go back',
      }),
    );

    expect(mockBack).toHaveBeenCalledTimes(1);
    expect(mockPush).not.toHaveBeenCalled();
  });

  test('keeps the friendly fallback for a missing session ID', async () => {
    mockSearchParams = {};
    const { getByText, queryByRole } = await render(
      <LocationCheckRoute />,
    );

    expect(
      getByText(
        /We could not open this attendance step because the session link is incomplete/,
      ),
    ).toBeTruthy();
    expect(
      queryByRole('button', {
        name: 'Allow location access and check classroom location',
      }),
    ).toBeNull();
    expect(mockBack).not.toHaveBeenCalled();
    expect(mockPush).not.toHaveBeenCalled();
  });

  test('does not expose the protected location screen without an authenticated session', async () => {
    mockAuthSession = { status: 'unauthenticated' };

    const { queryByRole } = await render(<LocationCheckRoute />);

    expect(
      queryByRole('button', {
        name: 'Allow location access and check classroom location',
      }),
    ).toBeNull();
    expect(mockPush).not.toHaveBeenCalled();
  });
});
