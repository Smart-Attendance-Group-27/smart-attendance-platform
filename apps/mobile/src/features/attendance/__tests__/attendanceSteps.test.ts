import { describe, expect, test } from '@jest/globals';

import { myAttendanceFixtures } from '../__fixtures__/myAttendance';
import type { MyAttendance } from '../types/myAttendance';
import {
  buildAttendanceSteps,
  nextCheckInAction,
  stepProgress,
  summarizeAttendance,
} from '../utils/attendanceSteps';

const active = myAttendanceFixtures['attendance-session-active'];
const waived = myAttendanceFixtures['attendance-session-geofence-waived'];

function stateOf(attendance: MyAttendance, key: string) {
  return buildAttendanceSteps(attendance, null).find((step) => step.key === key)?.state;
}

describe('buildAttendanceSteps', () => {
  test('follows the session requirements', () => {
    const keys = buildAttendanceSteps(myAttendanceFixtures['attendance-session-geofence-only'], null)
      .map((step) => step.key);
    expect(keys).toEqual(['location', 'attendance']);
  });

  test('keeps waived location separate from a pass even when the reading failed', () => {
    expect(waived.verification.geofenceStatus).toBe('failed');
    expect(stateOf(waived, 'location')).toBe('waived');
    expect(stateOf(waived, 'face')).toBe('active');
  });

  test('a waived step is not counted as completed', () => {
    const progress = stepProgress(buildAttendanceSteps(waived, null));
    expect(progress.completed).toBe(0);
    expect(progress.total).toBe(3);
  });

  test('marks the QR step partial when some required checks were missed', () => {
    const steps = buildAttendanceSteps(myAttendanceFixtures['attendance-session-left-early'], {
      sessionId: 'attendance-session-left-early', qrEnabled: true, checkedInAt: null,
      requiredCount: 3, passedCount: 1, activeBatch: null, batches: [],
    });
    expect(steps.find((step) => step.key === 'qr')).toMatchObject({
      state: 'partial', detail: '1 of 3 required checks completed',
    });
  });

  test('marks the QR step failed when none of the required checks were passed', () => {
    const steps = buildAttendanceSteps(myAttendanceFixtures['attendance-session-closed'], {
      sessionId: 'attendance-session-closed', qrEnabled: true, checkedInAt: null,
      requiredCount: 2, passedCount: 0, activeBatch: null, batches: [],
    });
    expect(steps.find((step) => step.key === 'qr')?.state).toBe('failed');
  });
});

describe('summarizeAttendance', () => {
  test.each([
    ['attendance-session-closed', 'Present', 'success'],
    ['attendance-session-left-early', 'Left early', 'warning'],
    ['attendance-session-manual-absent', 'Absent', 'error'],
  ])('summarises %s as %s', (sessionId, title, tone) => {
    expect(summarizeAttendance(myAttendanceFixtures[sessionId])).toMatchObject({ title, tone });
  });
});

describe('nextCheckInAction', () => {
  test('starts with location when it is required', () => {
    expect(nextCheckInAction(active)).toBe('start_check_in');
  });

  test('goes straight to face once location is waived', () => {
    expect(nextCheckInAction(waived)).toBe('continue_to_face');
  });

  test('offers nothing once the student has checked in', () => {
    expect(nextCheckInAction(myAttendanceFixtures['attendance-session-checked-in'])).toBe('none');
  });
});
