import { describe, expect, jest, test } from '@jest/globals';
import {
  act,
  fireEvent,
  render,
} from '@testing-library/react-native';

import { CheckInResultScreen } from '../screens/CheckInResultScreen';

type SuccessfulCheckInOutcome = 'checked_in' | 'present' | 'late';

function createAttendanceService(
  status: SuccessfulCheckInOutcome,
  checkInTime: string,
) {
  return {
    getAttendanceSession: jest.fn(async () => ({
      status: 'unavailable' as const,
    })),
    getCheckInResult: jest.fn(async () => ({
      status: 'available' as const,
      result: {
        sessionId: 'attendance-session-active',
        status,
        checkInTime,
      },
    })),
  };
}

async function renderResult(
  status: SuccessfulCheckInOutcome = 'checked_in',
  checkInTime = '2026-07-20T10:02:00+05:30',
  onOpenQrScanner?: () => void,
) {
  const onReturnHome = jest.fn();
  const attendanceService = createAttendanceService(status, checkInTime);

  const screen = await render(
      <CheckInResultScreen
        attendanceService={attendanceService}
        onOpenQrScanner={onOpenQrScanner}
        onReturnHome={onReturnHome}
        sessionId="attendance-session-active"
      />,
    );

  return {
    ...screen,
    attendanceService,
    onReturnHome,
  };
}

describe('CheckInResultScreen', () => {
  test('shows a provisional Checked In result with its time and return action', async () => {
    const {
      findByText,
      getAllByText,
      getByLabelText,
      getByRole,
      queryByText,
    } = await renderResult();

    expect(await findByText('Check-in Confirmed')).toBeTruthy();
    expect(getByRole('header', { name: 'Check-in Confirmed' })).toBeTruthy();
    expect(getByRole('button', {
      name: 'Return to student home',
    })).toBeTruthy();
    expect(await findByText('Checked In')).toBeTruthy();
    expect(await findByText('Checked in at')).toBeTruthy();
    expect(await findByText('10:02')).toBeTruthy();
    expect(
      getByLabelText('Attendance check-in completed successfully'),
    ).toBeTruthy();
    expect(
      getByLabelText(
        'Attendance check-in progress: Location, Face, Complete',
      ),
    ).toBeTruthy();
    expect(getAllByText('Verified')).toHaveLength(2);
    expect(queryByText('Late')).toBeNull();
  });

  test('does not claim a final attendance status after initial check-in', async () => {
    const { findByText, queryByText } = await renderResult();

    await findByText('Check-in Confirmed');

    // The final present/late decision belongs to session finalization.
    expect(queryByText('On-time')).toBeNull();
    expect(queryByText('Final Attendance')).toBeNull();
    expect(
      queryByText('Your attendance has been recorded successfully.'),
    ).toBeNull();
    expect(
      await findByText(/final attendance is confirmed when your lecturer closes/i),
    ).toBeTruthy();
  });

  test('shows a final On-time result when the session was already finalized', async () => {
    const { findByText } = await renderResult(
      'present',
      '2026-07-20T10:02:00+05:30',
    );

    expect(await findByText('On-time')).toBeTruthy();
    expect(await findByText('Final Attendance')).toBeTruthy();
    expect(
      await findByText('Your attendance has been recorded successfully.'),
    ).toBeTruthy();
  });

  test('shows Late as a successful result rather than a failure', async () => {
    const {
      findByText,
      getByLabelText,
      queryByText,
    } = await renderResult('late', '2026-07-20T10:18:00+05:30');

    expect(await findByText('Check-in Confirmed')).toBeTruthy();
    expect(await findByText('Late')).toBeTruthy();
    expect(
      await findByText('Your attendance has been recorded as late.'),
    ).toBeTruthy();
    expect(await findByText('10:18')).toBeTruthy();
    expect(
      getByLabelText(
        'Attendance status: Late. Your attendance has been recorded as late.',
      ),
    ).toBeTruthy();
    expect(
      queryByText(/Face verification failed|Attendance failed|Try Again/i),
    ).toBeNull();
  });

  test('formats a fixed check-in timestamp using attendance time conventions', async () => {
    const { findByText, queryByText } = await renderResult(
      'present',
      '2026-07-20T18:45:00+05:30',
    );

    expect(await findByText('18:45')).toBeTruthy();
    expect(queryByText('Time unavailable')).toBeNull();
  });

  test('calls the supplied Return to Home callback', async () => {
    const { findByRole, onReturnHome } = await renderResult();

    fireEvent.press(
      await findByRole('button', {
        name: 'Return to student home',
      }),
    );

    expect(onReturnHome).toHaveBeenCalledTimes(1);
  });

  test('does not present QR as a mandatory check-in step', async () => {
    const {
      findByText,
      queryByRole,
      queryByText,
    } = await renderResult();

    await findByText('Check-in Confirmed');

    expect(
      queryByText(
        /Scan QR|Waiting for QR|QR verification required|Continue to QR|QR required/i,
      ),
    ).toBeNull();
    expect(
      queryByRole('button', { name: /QR scanner/i }),
    ).toBeNull();
  });

  test('shows and invokes the optional QR preview action when supplied', async () => {
    const onOpenQrScanner = jest.fn();
    const screen = await renderResult(
      'present',
      '2026-07-20T10:02:00+05:30',
      onOpenQrScanner,
    );

    fireEvent.press(
      await screen.findByRole('button', {
        name: 'Open QR scanner preview',
      }),
    );

    expect(onOpenQrScanner).toHaveBeenCalledTimes(1);
  });

  test('exposes an accessible busy state while loading the result', async () => {
    let resolveResult:
      | ((value: {
          status: 'available';
          result: {
            sessionId: string;
            status: 'checked_in';
            checkInTime: string;
          };
        }) => void)
      | undefined;
    const pendingResult = new Promise<{
      status: 'available';
      result: {
        sessionId: string;
        status: 'checked_in';
        checkInTime: string;
      };
    }>((resolve) => {
      resolveResult = resolve;
    });
    const attendanceService = {
      getAttendanceSession: jest.fn(async () => ({
        status: 'unavailable' as const,
      })),
      getCheckInResult: jest.fn(() => pendingResult),
    };
    const screen = await render(
      <CheckInResultScreen
        attendanceService={attendanceService}
        onReturnHome={jest.fn()}
        sessionId="attendance-session-active"
      />,
    );

    const loadingIndicator = screen.getByRole('progressbar', {
      name: 'Loading check-in result',
    });

    expect(loadingIndicator.props.accessibilityState).toEqual(
      expect.objectContaining({ busy: true }),
    );

    await act(async () => {
      resolveResult?.({
        status: 'available',
        result: {
          sessionId: 'attendance-session-active',
          status: 'checked_in',
          checkInTime: '2026-07-20T10:02:00+05:30',
        },
      });
      await pendingResult;
    });
  });

  test('shows a friendly safe return state when no result is available', async () => {
    const onReturnHome = jest.fn();
    const attendanceService = {
      getAttendanceSession: jest.fn(async () => ({
        status: 'unavailable' as const,
      })),
      getCheckInResult: jest.fn(async () => ({
        status: 'unavailable' as const,
      })),
    };
    const {
      findByRole,
      findByText,
      queryByText,
    } = await render(
      <CheckInResultScreen
        attendanceService={attendanceService}
        onReturnHome={onReturnHome}
        sessionId="attendance-session-missing"
      />,
    );

    expect(
      await findByText("We couldn't load your check-in result."),
    ).toBeTruthy();
    expect(queryByText(/undefined|null|internal error/i)).toBeNull();

    fireEvent.press(
      await findByRole('button', {
        name: 'Return to student home',
      }),
    );

    expect(onReturnHome).toHaveBeenCalledTimes(1);
  });
});
