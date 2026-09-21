import { describe, expect, jest, test } from '@jest/globals';
import { fireEvent, render, waitFor } from '@testing-library/react-native';

import { myAttendanceFixtures } from '../__fixtures__/myAttendance';
import { AttendanceProgressScreen } from '../screens/AttendanceProgressScreen';
import type { AttendanceService } from '../services/attendanceService';
import type { QrProgressService } from '../../qr/services/qrProgressService';

jest.mock('expo-router', () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const React = require('react');
  return { useFocusEffect: (callback: () => void | (() => void)) => React.useEffect(callback, [callback]) };
});

function serviceFor(sessionId: string): AttendanceService {
  return {
    async getAttendanceSession() { return { status: 'unavailable' }; },
    async getMyAttendance() {
      return { status: 'loaded', attendance: myAttendanceFixtures[sessionId] };
    },
    async checkIn() {
      return { status: 'loaded', outcome: 'checked_in', initialCheckIn: null, missingRequirements: [] };
    },
  };
}

describe('AttendanceProgressScreen', () => {
  test('keeps initial check-in distinct from final attendance', async () => {
    const screen = await render(<AttendanceProgressScreen
      attendanceService={serviceFor('attendance-session-checked-in')}
      onReturnHome={jest.fn()}
      onStartCheckIn={jest.fn()}
      sessionId="attendance-session-checked-in"
    />);

    expect(await screen.findByText('Initial check-in complete (on time)')).toBeTruthy();
    expect(screen.getByText('Awaiting final attendance')).toBeTruthy();
    expect(screen.queryByText('Final: Present')).toBeNull();
  });

  test('shows a lecturer-set final decision separately', async () => {
    const screen = await render(<AttendanceProgressScreen
      attendanceService={serviceFor('attendance-session-manual-absent')}
      onReturnHome={jest.fn()}
      onStartCheckIn={jest.fn()}
      sessionId="attendance-session-manual-absent"
    />);

    expect(await screen.findByText('Final: Absent')).toBeTruthy();
    expect(screen.getByText('Set by your lecturer')).toBeTruthy();
  });

  test('shows a voided batch without counting it as required or passed', async () => {
    const attendanceService: AttendanceService = {
      ...serviceFor('attendance-session-checked-in'),
      async getMyAttendance() {
        return { status: 'loaded', attendance: {
          ...myAttendanceFixtures['attendance-session-checked-in'], qrEnabled: true,
        } };
      },
    };
    const qrProgressService: QrProgressService = {
      async getQrProgress(sessionId) {
        return { status: 'loaded', progress: {
          sessionId, qrEnabled: true, checkedInAt: '2026-07-20T10:02:00+05:30',
          requiredCount: 0, passedCount: 0, activeBatch: null,
          batches: [{
            qrSessionId: 'batch-1', mode: 'static', activatedAt: '2026-07-20T10:05:00+05:30',
            deactivatedAt: '2026-07-20T10:07:00+05:30', expiresAt: '2026-07-20T10:10:00+05:30',
            voided: true, required: false, passed: false,
          }],
        } };
      },
    };
    const screen = await render(<AttendanceProgressScreen
      attendanceService={attendanceService}
      qrProgressService={qrProgressService}
      onReturnHome={jest.fn()}
      onStartCheckIn={jest.fn()}
      sessionId="attendance-session-checked-in"
    />);

    expect(await screen.findByText('0/0 required batches passed')).toBeTruthy();
    expect(screen.getByText('Batch 1: Voided')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Scan QR' })).toBeNull();
  });

  test('retries C01 once after complete evidence and refreshes C02', async () => {
    const checkIn = jest.fn(async () => ({
      status: 'loaded' as const,
      outcome: 'checked_in' as const,
      initialCheckIn: myAttendanceFixtures['attendance-session-checked-in'].initialCheckIn,
      missingRequirements: [],
    }));
    let reads = 0;
    const service: AttendanceService = {
      async getAttendanceSession() { return { status: 'unavailable' }; },
      async getMyAttendance() {
        reads += 1;
        return { status: 'loaded', attendance: reads === 1
          ? myAttendanceFixtures['attendance-session-recovery']
          : myAttendanceFixtures['attendance-session-checked-in'] };
      },
      checkIn,
    };
    const screen = await render(<AttendanceProgressScreen
      attendanceService={service}
      onReturnHome={jest.fn()}
      onStartCheckIn={jest.fn()}
      sessionId="attendance-session-recovery"
    />);

    expect(await screen.findByText('Initial check-in complete (on time)')).toBeTruthy();
    expect(checkIn).toHaveBeenCalledTimes(1);
    expect(checkIn).toHaveBeenCalledWith('attendance-session-recovery');
    expect(reads).toBe(2);
    fireEvent.press(screen.getByRole('button', { name: 'Return home' }));
    await waitFor(() => expect(checkIn).toHaveBeenCalledTimes(1));
  });
});
