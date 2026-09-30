import { describe, expect, jest, test } from '@jest/globals';
import { fireEvent, render, waitFor, within } from '@testing-library/react-native';

import { myAttendanceFixtures } from '../__fixtures__/myAttendance';
import { AttendanceProgressScreen } from '../screens/AttendanceProgressScreen';
import type { AttendanceService } from '../services/attendanceService';
import type { MyAttendance } from '../types/myAttendance';
import type { QrProgress } from '../../qr/types/qrProgress';
import type { QrProgressService } from '../../qr/services/qrProgressService';

jest.mock('expo-router', () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const React = require('react');
  return { useFocusEffect: (callback: () => void | (() => void)) => React.useEffect(callback, [callback]) };
});

function serviceWith(attendance: MyAttendance, overrides: Partial<AttendanceService> = {}): AttendanceService {
  return {
    async getAttendanceSession() { return { status: 'unavailable' }; },
    async getMyAttendance() { return { status: 'loaded', attendance }; },
    async checkIn() {
      return { status: 'loaded', outcome: 'checked_in', initialCheckIn: null, missingRequirements: [] };
    },
    async startVerificationWithoutLocation() { return { status: 'started', initialCheckIn: null }; },
    ...overrides,
  };
}

function serviceFor(sessionId: string): AttendanceService {
  return serviceWith(myAttendanceFixtures[sessionId]);
}

function qrServiceWith(progress: Omit<QrProgress, 'sessionId'>): QrProgressService {
  return {
    async getQrProgress(sessionId) {
      return { status: 'loaded', progress: { sessionId, ...progress } };
    },
  };
}

const CHECKED_IN_AT = '2026-07-20T10:02:00+05:30';

function batch(id: string, overrides: { required?: boolean; passed?: boolean; voided?: boolean } = {}) {
  return {
    qrSessionId: id, mode: 'static', activatedAt: '2026-07-20T10:30:00+05:30',
    deactivatedAt: '2026-07-20T10:35:00+05:30', expiresAt: '2026-07-20T10:40:00+05:30',
    voided: false, required: true, passed: false, ...overrides,
  };
}

async function renderScreen(
  attendanceService: AttendanceService,
  sessionId: string,
  extra: {
    qrProgressService?: QrProgressService;
    onStartCheckIn?: () => void;
    onContinueToFaceVerification?: (locationWaived: boolean) => void;
  } = {},
) {
  return render(<AttendanceProgressScreen
    attendanceService={attendanceService}
    onContinueToFaceVerification={extra.onContinueToFaceVerification}
    onReturnHome={jest.fn()}
    onStartCheckIn={extra.onStartCheckIn ?? jest.fn()}
    qrProgressService={extra.qrProgressService}
    sessionId={sessionId}
  />);
}

describe('AttendanceProgressScreen', () => {
  test('shows pending and active steps before the student starts', async () => {
    const onStartCheckIn = jest.fn();
    const screen = await renderScreen(serviceFor('attendance-session-active'), 'attendance-session-active', {
      onStartCheckIn,
    });

    const location = await screen.findByTestId('attendance-step-location');
    expect(location.props.accessibilityLabel).toContain('Action needed');
    expect(screen.getByTestId('attendance-step-face').props.accessibilityLabel).toContain('Pending');
    expect(screen.getByText('Not checked in')).toBeTruthy();

    fireEvent.press(screen.getByRole('button', { name: 'Start check-in' }));
    expect(onStartCheckIn).toHaveBeenCalledTimes(1);
  });

  test('keeps the initial check-in distinct from final attendance', async () => {
    const screen = await renderScreen(serviceFor('attendance-session-checked-in'), 'attendance-session-checked-in');

    expect(await screen.findByText('Checked in')).toBeTruthy();
    expect(screen.getByText('Final attendance is decided when the session closes.')).toBeTruthy();
    expect(screen.getByTestId('attendance-step-location').props.accessibilityLabel).toContain('Completed');
    expect(screen.getByTestId('attendance-step-face').props.accessibilityLabel).toContain('Completed');
    expect(screen.getByTestId('attendance-step-attendance').props.accessibilityLabel).toContain('In progress');
    expect(screen.queryByText('Present')).toBeNull();
  });

  test('shows a waived location step as waived, never as completed', async () => {
    const screen = await renderScreen(
      serviceFor('attendance-session-geofence-waived'),
      'attendance-session-geofence-waived',
    );

    const location = await screen.findByTestId('attendance-step-location');
    expect(location.props.accessibilityLabel).toContain('Waived');
    expect(location.props.accessibilityLabel).not.toContain('Completed');
    expect(within(location).getByText('Waived for this session by your lecturer')).toBeTruthy();
    expect(screen.getByTestId('attendance-step-face').props.accessibilityLabel).toContain('Action needed');
    expect(screen.queryByRole('button', { name: 'Start check-in' })).toBeNull();
  });

  test('continues a student who failed location to face verification after a waiver', async () => {
    const startVerificationWithoutLocation = jest.fn(async () => ({
      status: 'started' as const, initialCheckIn: null,
    }));
    const onContinueToFaceVerification = jest.fn();
    const screen = await renderScreen(
      serviceWith(myAttendanceFixtures['attendance-session-geofence-waived'], { startVerificationWithoutLocation }),
      'attendance-session-geofence-waived',
      { onContinueToFaceVerification },
    );

    fireEvent.press(await screen.findByRole('button', { name: 'Continue to face verification' }));

    await waitFor(() => expect(onContinueToFaceVerification).toHaveBeenCalledWith(true));
    expect(startVerificationWithoutLocation).toHaveBeenCalledWith('attendance-session-geofence-waived');
  });

  test('shows a failed step when verification failed and no waiver applies', async () => {
    const failed: MyAttendance = {
      ...myAttendanceFixtures['attendance-session-active'],
      canStartCheckIn: false,
      verification: {
        ...myAttendanceFixtures['attendance-session-active'].verification,
        attemptStatus: 'failed', geofenceStatus: 'failed', failureReason: 'OUTSIDE_GEOFENCE',
      },
    };
    const screen = await renderScreen(serviceWith(failed), 'attendance-session-active');

    expect(await screen.findByText('Verification failed')).toBeTruthy();
    expect(screen.getByTestId('attendance-step-location').props.accessibilityLabel).toContain('Failed');
    expect(screen.queryByRole('button', { name: 'Start check-in' })).toBeNull();
  });

  test('shows QR progress and opens the scanner for an open required check', async () => {
    const attendance = myAttendanceFixtures['attendance-session-checked-in'];
    const onOpenQrScanner = jest.fn();
    const qrProgressService = qrServiceWith({
      qrEnabled: true, checkedInAt: CHECKED_IN_AT, requiredCount: 2, passedCount: 1,
      activeBatch: {
        qrSessionId: 'batch-2', mode: 'static', activatedAt: '2026-07-20T11:00:00+05:30',
        expiresAt: '2099-01-01T00:00:00Z', required: true, passed: false,
      },
      batches: [batch('batch-2'), batch('batch-1', { passed: true })],
    });
    const screen = await render(<AttendanceProgressScreen
      attendanceService={serviceWith(attendance)}
      onOpenQrScanner={onOpenQrScanner}
      onReturnHome={jest.fn()}
      onStartCheckIn={jest.fn()}
      qrProgressService={qrProgressService}
      sessionId="attendance-session-checked-in"
    />);

    expect(await screen.findByText('Scan the QR code now · 1 of 2 required checks completed')).toBeTruthy();
    fireEvent.press(screen.getByRole('button', { name: 'Scan QR' }));
    expect(onOpenQrScanner).toHaveBeenCalledWith('batch-2');
  });

  test('does not show a voided batch as a missing required check', async () => {
    const qrProgressService = qrServiceWith({
      qrEnabled: true, checkedInAt: CHECKED_IN_AT, requiredCount: 0, passedCount: 0,
      activeBatch: null, batches: [batch('batch-1', { voided: true, required: false })],
    });
    const screen = await renderScreen(
      serviceFor('attendance-session-checked-in'),
      'attendance-session-checked-in',
      { qrProgressService },
    );

    expect(await screen.findByText('Voided')).toBeTruthy();
    expect(screen.getByText('No QR checks yet. Waiting for your lecturer.')).toBeTruthy();
    expect(screen.queryByText('Missed')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Scan QR' })).toBeNull();
  });

  test('shows a closed session with no required QR checks as not required', async () => {
    const qrProgressService = qrServiceWith({
      qrEnabled: true, checkedInAt: CHECKED_IN_AT, requiredCount: 0, passedCount: 0,
      activeBatch: null, batches: [],
    });
    const screen = await renderScreen(
      serviceFor('attendance-session-closed'),
      'attendance-session-closed',
      { qrProgressService },
    );

    const qr = await screen.findByTestId('attendance-step-qr');
    expect(qr.props.accessibilityLabel).toContain('Not required');
    expect(screen.getAllByText('Present').length).toBeGreaterThan(0);
  });

  test('explains a left early result', async () => {
    const qrProgressService = qrServiceWith({
      qrEnabled: true, checkedInAt: CHECKED_IN_AT, requiredCount: 2, passedCount: 1,
      activeBatch: null, batches: [batch('batch-2'), batch('batch-1', { passed: true })],
    });
    const screen = await renderScreen(
      serviceFor('attendance-session-left-early'),
      'attendance-session-left-early',
      { qrProgressService },
    );

    expect((await screen.findAllByText('Left early')).length).toBeGreaterThan(0);
    expect(screen.getByText(
      'Partial attendance. You completed some, but not all, required QR checks.',
    )).toBeTruthy();
    expect(screen.getByTestId('attendance-step-qr').props.accessibilityLabel).toContain('Partial');
    expect(screen.getByText('Missed')).toBeTruthy();
  });

  test('shows a lecturer-set absent result', async () => {
    const screen = await renderScreen(
      serviceFor('attendance-session-manual-absent'),
      'attendance-session-manual-absent',
    );

    expect(await screen.findByText('Absent')).toBeTruthy();
    expect(screen.getByText('Set by your lecturer.')).toBeTruthy();
    expect(screen.getByTestId('attendance-step-attendance').props.accessibilityLabel).toContain('Failed');
  });

  test('shows the cancellation reason for a cancelled session', async () => {
    const screen = await renderScreen(serviceFor('attendance-session-cancelled'), 'attendance-session-cancelled');

    expect((await screen.findAllByText('Session cancelled')).length).toBeGreaterThan(0);
    expect(screen.getByText('The lecturer is unwell.')).toBeTruthy();
  });

  test('falls back to a plain message when no cancellation reason was recorded', async () => {
    const screen = await renderScreen(
      serviceFor('attendance-session-cancelled-no-reason'),
      'attendance-session-cancelled-no-reason',
    );

    expect((await screen.findAllByText('Session cancelled')).length).toBeGreaterThan(0);
    expect(screen.getByText('No reason was recorded.')).toBeTruthy();
  });

  test('shows an error with a retry action', async () => {
    let calls = 0;
    const service = serviceWith(myAttendanceFixtures['attendance-session-checked-in'], {
      async getMyAttendance() {
        calls += 1;
        return calls === 1
          ? { status: 'network-error' as const }
          : { status: 'loaded' as const, attendance: myAttendanceFixtures['attendance-session-checked-in'] };
      },
    });
    const screen = await renderScreen(service, 'attendance-session-checked-in');

    expect(await screen.findByText('Could not load attendance. Check your connection and try again.')).toBeTruthy();
    fireEvent.press(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('Checked in')).toBeTruthy();
  });

  test('retries the check-in once after complete evidence and refreshes the state', async () => {
    const checkIn = jest.fn(async () => ({
      status: 'loaded' as const,
      outcome: 'checked_in' as const,
      initialCheckIn: myAttendanceFixtures['attendance-session-checked-in'].initialCheckIn,
      missingRequirements: [],
    }));
    let reads = 0;
    const service = serviceWith(myAttendanceFixtures['attendance-session-recovery'], {
      async getMyAttendance() {
        reads += 1;
        return { status: 'loaded', attendance: reads === 1
          ? myAttendanceFixtures['attendance-session-recovery']
          : myAttendanceFixtures['attendance-session-checked-in'] };
      },
      checkIn,
    });
    const screen = await renderScreen(service, 'attendance-session-recovery');

    expect(await screen.findByText('Checked in')).toBeTruthy();
    expect(checkIn).toHaveBeenCalledTimes(1);
    expect(checkIn).toHaveBeenCalledWith('attendance-session-recovery');
    expect(reads).toBe(2);
    fireEvent.press(screen.getByRole('button', { name: 'Return home' }));
    await waitFor(() => expect(checkIn).toHaveBeenCalledTimes(1));
  });
});
