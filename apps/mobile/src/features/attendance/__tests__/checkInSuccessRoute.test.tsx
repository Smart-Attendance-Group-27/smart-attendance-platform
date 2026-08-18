import {
  beforeEach,
  describe,
  expect,
  jest,
  test,
} from '@jest/globals';
import { fireEvent, render } from '@testing-library/react-native';

import CheckInSuccessRoute from '../../../app/(student)/attendance/[sessionId]/check-in-success';

const mockPush = jest.fn();
const mockReplace = jest.fn();
let mockSearchParams: {
  sessionId?: string | string[];
};

jest.mock('../../auth/context/AuthContext', () => ({
  useAuth: () => ({
    session: {
      status: 'authenticated',
      accessToken: 'test-access-token',
    },
  }),
}));

jest.mock('../services/coreApiAttendanceService', () => {
  const actual = jest.requireActual('../services/mockAttendanceService') as {
    MockAttendanceService: new () => unknown;
  };

  return {
    CoreApiAttendanceService: actual.MockAttendanceService,
  };
});

jest.mock('expo-router', () => ({
  useLocalSearchParams: () => mockSearchParams,
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
  }),
}));

describe('CheckInSuccessRoute', () => {
  beforeEach(() => {
    mockPush.mockClear();
    mockReplace.mockClear();
    mockSearchParams = {
      sessionId: 'attendance-session-active',
    };
  });

  test('loads the On-time result using the normalized session ID', async () => {
    mockSearchParams = {
      sessionId: [' attendance-session-active ', 'ignored-session'],
    };
    const screen = await render(<CheckInSuccessRoute />);

    expect(await screen.findByText('Check-in Confirmed')).toBeTruthy();
    expect(await screen.findByText('On-time')).toBeTruthy();
    expect(await screen.findByText('10:02')).toBeTruthy();
    expect(mockPush).not.toHaveBeenCalled();
    expect(mockReplace).not.toHaveBeenCalled();
  });

  test('loads the deterministic Late result as a successful check-in', async () => {
    mockSearchParams = {
      sessionId: 'attendance-session-late',
    };
    const screen = await render(<CheckInSuccessRoute />);

    expect(await screen.findByText('Check-in Confirmed')).toBeTruthy();
    expect(await screen.findByText('Late')).toBeTruthy();
    expect(await screen.findByText('10:18')).toBeTruthy();
    expect(screen.queryByText(/Attendance failed|Try Again/i)).toBeNull();
    expect(mockPush).not.toHaveBeenCalled();
    expect(mockReplace).not.toHaveBeenCalled();
  });

  test('replaces the completed flow with student Home only after Return is pressed', async () => {
    const screen = await render(<CheckInSuccessRoute />);

    fireEvent.press(
      await screen.findByRole('button', {
        name: 'Return to student home',
      }),
    );

    expect(mockReplace).toHaveBeenCalledTimes(1);
    expect(mockReplace).toHaveBeenCalledWith('/(student)/(tabs)');
    expect(mockPush).not.toHaveBeenCalled();
  });

  test('opens the temporary QR scanner preview only when its action is pressed', async () => {
    const screen = await render(<CheckInSuccessRoute />);

    expect(mockPush).not.toHaveBeenCalled();

    fireEvent.press(
      await screen.findByRole('button', {
        name: 'Open QR scanner preview',
      }),
    );

    expect(mockPush).toHaveBeenCalledTimes(1);
    expect(mockPush).toHaveBeenCalledWith({
      pathname: '/(student)/attendance/[sessionId]/qr-scanner',
      params: {
        sessionId: 'attendance-session-active',
      },
    });
    expect(mockReplace).not.toHaveBeenCalled();
  });

  test('keeps the friendly fallback for a missing session ID', async () => {
    mockSearchParams = {};
    const screen = await render(<CheckInSuccessRoute />);

    expect(
      screen.getByText(
        /We could not open this attendance step because the session link is incomplete/,
      ),
    ).toBeTruthy();
    expect(
      screen.queryByRole('button', {
        name: 'Return to student home',
      }),
    ).toBeNull();
    expect(mockPush).not.toHaveBeenCalled();
    expect(mockReplace).not.toHaveBeenCalled();
  });
});
