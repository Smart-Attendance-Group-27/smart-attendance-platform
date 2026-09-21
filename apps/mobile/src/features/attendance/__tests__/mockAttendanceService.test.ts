import { beforeEach, describe, expect, test } from '@jest/globals';

import { resetMockAttendanceStore } from '../__fixtures__/mockAttendanceStore';
import { MockAttendanceService } from '../services/mockAttendanceService';

beforeEach(resetMockAttendanceStore);

describe('MockAttendanceService', () => {
  test('provides separate initial and final states', async () => {
    const service = new MockAttendanceService();
    const checkedIn = await service.getMyAttendance('attendance-session-checked-in');
    const closed = await service.getMyAttendance('attendance-session-closed');
    expect(checkedIn.status === 'loaded' && checkedIn.attendance.initialCheckIn?.status)
      .toBe('checked_in');
    expect(checkedIn.status === 'loaded' && checkedIn.attendance.finalAttendance).toBeNull();
    expect(closed.status === 'loaded' && closed.attendance.finalAttendance?.status)
      .toBe('present');
  });

  test('recovers a lost check-in hook call using C01', async () => {
    const service = new MockAttendanceService();
    await expect(service.checkIn('attendance-session-recovery')).resolves.toEqual({
      status: 'loaded', outcome: 'checked_in',
      initialCheckIn: { status: 'checked_in', checkedInAt: '2026-07-20T10:04:00+05:30' },
      missingRequirements: [],
    });
    const result = await service.getMyAttendance('attendance-session-recovery');
    expect(result.status === 'loaded' && result.attendance.initialCheckIn?.status)
      .toBe('checked_in');
  });

  test('keeps incomplete evidence from becoming checked in', async () => {
    const result = await new MockAttendanceService().checkIn('attendance-session-active');
    expect(result).toEqual({
      status: 'loaded', outcome: 'incomplete', initialCheckIn: null,
      missingRequirements: ['geofence'],
    });
  });
});
