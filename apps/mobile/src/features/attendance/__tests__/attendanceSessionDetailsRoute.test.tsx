import {
  beforeEach,
  describe,
  expect,
  jest,
  test,
} from '@jest/globals';
import { fireEvent, render } from '@testing-library/react-native';

import AttendanceSessionDetailsRoute from '../../../app/(student)/attendance/[sessionId]';

const mockBack = jest.fn();
const mockPush = jest.fn();
let mockSearchParams: {
  sessionId?: string | string[];
};

jest.mock('expo-router', () => ({
  useLocalSearchParams: () => mockSearchParams,
  useRouter: () => ({
    back: mockBack,
    push: mockPush,
  }),
}));

describe('AttendanceSessionDetailsRoute', () => {
  beforeEach(() => {
    mockBack.mockClear();
    mockPush.mockClear();
    mockSearchParams = {
      sessionId: 'attendance-session-active',
    };
  });

  test('opens location check with the normalized session ID', async () => {
    mockSearchParams = {
      sessionId: [' attendance-session-active ', 'ignored-session'],
    };
    const { findByRole } = await render(<AttendanceSessionDetailsRoute />);

    fireEvent.press(
      await findByRole('button', {
        name: 'Start attendance check-in',
      }),
    );

    expect(mockPush).toHaveBeenCalledWith({
      pathname: '/(student)/attendance/[sessionId]/location-check',
      params: {
        sessionId: 'attendance-session-active',
      },
    });
  });

  test('uses router back for the screen back action', async () => {
    const { findByRole } = await render(<AttendanceSessionDetailsRoute />);

    fireEvent.press(
      await findByRole('button', {
        name: 'Go back',
      }),
    );

    expect(mockBack).toHaveBeenCalledTimes(1);
  });

  test('keeps the friendly fallback for a missing session ID', async () => {
    mockSearchParams = {};
    const { getByText, queryByRole } = await render(
      <AttendanceSessionDetailsRoute />,
    );

    expect(
      getByText(
        /We could not open this attendance step because the session link is incomplete/,
      ),
    ).toBeTruthy();
    expect(
      queryByRole('button', {
        name: 'Start attendance check-in',
      }),
    ).toBeNull();
    expect(mockPush).not.toHaveBeenCalled();
  });
});
