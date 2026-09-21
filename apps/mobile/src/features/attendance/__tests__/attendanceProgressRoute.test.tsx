import { afterEach, beforeEach, describe, expect, jest, test } from '@jest/globals';
import { fireEvent, render } from '@testing-library/react-native';

import AttendanceProgressRoute from '../../../app/(student)/attendance/[sessionId]/progress';
import { resetMockAttendanceStore } from '../__fixtures__/mockAttendanceStore';

const mockPush = jest.fn();
const mockReplace = jest.fn();
let mockSearchParams: { sessionId?: string | string[] };
let mockAuthSession:
  | { status: 'authenticated'; accessToken: string }
  | { status: 'unauthenticated' };

jest.mock('expo-router', () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const React = require('react');
  return {
    useFocusEffect: (callback: () => void | (() => void)) => React.useEffect(callback, [callback]),
    useLocalSearchParams: () => mockSearchParams,
    useRouter: () => ({ push: mockPush, replace: mockReplace }),
  };
});

jest.mock('../../auth/context/AuthContext', () => ({
  useAuth: () => ({ session: mockAuthSession }),
}));

describe('AttendanceProgressRoute', () => {
  beforeEach(() => {
    process.env.EXPO_PUBLIC_API_MODE = 'mock';
    resetMockAttendanceStore();
    mockPush.mockClear();
    mockReplace.mockClear();
    mockSearchParams = { sessionId: [' attendance-session-checked-in ', 'ignored'] };
    mockAuthSession = { status: 'authenticated', accessToken: 'test-access-token' };
  });

  afterEach(() => { delete process.env.EXPO_PUBLIC_API_MODE; });

  test('opens frozen Progress route with a normalized session ID and returns home', async () => {
    const screen = await render(<AttendanceProgressRoute />);
    expect(await screen.findByText('Initial check-in complete (on time)')).toBeTruthy();
    fireEvent.press(screen.getByRole('button', { name: 'Return home' }));
    expect(mockReplace).toHaveBeenCalledWith('/(student)/(tabs)');
  });

  test('shows a friendly fallback for an incomplete link', async () => {
    mockSearchParams = {};
    const screen = await render(<AttendanceProgressRoute />);
    expect(screen.getByText('Attendance session link is incomplete.')).toBeTruthy();
    expect(mockPush).not.toHaveBeenCalled();
  });

  test('protects the route when there is no session', async () => {
    mockAuthSession = { status: 'unauthenticated' };
    const screen = await render(<AttendanceProgressRoute />);
    expect(screen.queryByText('Attendance progress')).toBeNull();
    expect(mockPush).not.toHaveBeenCalled();
  });
});
