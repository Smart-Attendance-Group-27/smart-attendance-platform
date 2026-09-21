import {
  beforeEach,
  describe,
  expect,
  jest,
  test,
} from '@jest/globals';
import { fireEvent, render, waitFor } from '@testing-library/react-native';

import LocationCheckRoute from '../../../app/(student)/attendance/[sessionId]/location-check';

const mockBack = jest.fn();
const mockPush = jest.fn();
const mockReplace = jest.fn();
let mockLocationResult:
  | { status: 'inside_geofence'; initialCheckIn?: { status: 'checked_in'; checkedInAt: string } }
  | { status: 'already_checked_in' };
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
    replace: mockReplace,
  }),
}));

jest.mock('../../auth/context/AuthContext', () => ({
  useAuth: () => ({ session: mockAuthSession }),
}));

jest.mock('../services/liveLocationService', () => ({
  LiveLocationService: class {
    async validateLocation() {
      return mockLocationResult;
    }
  },
}));

describe('LocationCheckRoute', () => {
  beforeEach(() => {
    mockBack.mockClear();
    mockPush.mockClear();
    mockReplace.mockClear();
    mockLocationResult = { status: 'inside_geofence' };
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

  test('replaces location verification with Progress after an existing check-in', async () => {
    mockLocationResult = { status: 'already_checked_in' };
    const screen = await render(<LocationCheckRoute />);

    await fireEvent.press(
      screen.getByRole('button', {
        name: 'Allow location access and check classroom location',
      }),
    );

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith({
        pathname:
          '/(student)/attendance/[sessionId]/progress',
        params: { sessionId: 'attendance-session-active' },
      });
    });
    expect(mockPush).not.toHaveBeenCalled();
  });

  test('goes directly to Progress when geofence validation completes initial check-in', async () => {
    mockLocationResult = {
      status: 'inside_geofence',
      initialCheckIn: { status: 'checked_in', checkedInAt: '2026-07-20T10:02:00+05:30' },
    };
    const screen = await render(<LocationCheckRoute />);

    fireEvent.press(screen.getByRole('button', {
      name: 'Allow location access and check classroom location',
    }));
    fireEvent.press(await screen.findByRole('button', { name: 'View attendance progress' }));

    expect(mockReplace).toHaveBeenCalledWith({
      pathname: '/(student)/attendance/[sessionId]/progress',
      params: { sessionId: 'attendance-session-active' },
    });
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
