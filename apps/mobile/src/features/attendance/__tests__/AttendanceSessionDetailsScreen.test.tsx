import { describe, expect, jest, test } from '@jest/globals';
import { fireEvent, render, waitFor } from '@testing-library/react-native';

import { AttendanceSessionDetailsScreen } from '../screens/AttendanceSessionDetailsScreen';
import { MockAttendanceService } from '../services/mockAttendanceService';

describe('AttendanceSessionDetailsScreen', () => {
  test('starts location check from an open session', async () => {
    const onStartCheckIn = jest.fn();
    const screen = await render(<AttendanceSessionDetailsScreen
      attendanceService={new MockAttendanceService()}
      onBack={jest.fn()}
      onStartCheckIn={onStartCheckIn}
      sessionId="attendance-session-active"
    />);
    fireEvent.press(await screen.findByRole('button', { name: 'Start attendance check-in' }));
    expect(onStartCheckIn).toHaveBeenCalledTimes(1);
  });

  test('redirects a checked-in session to Progress', async () => {
    const onOpenProgress = jest.fn();
    render(<AttendanceSessionDetailsScreen
      attendanceService={new MockAttendanceService()}
      onBack={jest.fn()}
      onOpenProgress={onOpenProgress}
      onStartCheckIn={jest.fn()}
      sessionId="attendance-session-checked-in"
    />);
    await waitFor(() => expect(onOpenProgress).toHaveBeenCalledWith('attendance-session-checked-in'));
  });

  test('shows unavailable when the student has no session', async () => {
    const screen = await render(<AttendanceSessionDetailsScreen
      attendanceService={new MockAttendanceService()}
      onBack={jest.fn()}
      onStartCheckIn={jest.fn()}
      sessionId="unknown"
    />);
    expect(await screen.findByText('Session unavailable')).toBeTruthy();
  });
});
