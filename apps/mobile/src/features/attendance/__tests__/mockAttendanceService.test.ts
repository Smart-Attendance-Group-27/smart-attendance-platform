import {
  describe,
  expect,
  test,
} from '@jest/globals';

import { MockAttendanceService } from '../services/mockAttendanceService';

const ISO_8601_PATTERN =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?(?:Z|[+-]\d{2}:\d{2})$/;

describe('MockAttendanceService', () => {
  test('returns the active session with details for check-in', async () => {
    const service = new MockAttendanceService();

    const result = await service.getAttendanceSession(
      'attendance-session-active',
    );

    expect(result.status).toBe('available');

    if (result.status !== 'available') {
      throw new Error('Expected the active session to be available');
    }

    expect(result.session).toEqual(
      expect.objectContaining({
        id: 'attendance-session-active',
        courseCode: 'CS3203',
        courseName: 'Software Engineering Project',
        sessionTitle: 'Architecture Review Lecture',
        lecturerName: 'Dr. N. Perera',
        venue: 'Level 3 Lab',
        checkInStatus: 'open',
      }),
    );
    expect(result.session.checkInOpensAt).toBeTruthy();
    expect(result.session.checkInClosesAt).toBeTruthy();
  });

  test('returns a closed session with its display details', async () => {
    const service = new MockAttendanceService();

    const result = await service.getAttendanceSession(
      'attendance-session-closed',
    );

    expect(result.status).toBe('available');

    if (result.status !== 'available') {
      throw new Error('Expected the closed session to be available');
    }

    expect(result.session.checkInStatus).toBe('closed');
    expect(result.session.courseCode).toBeTruthy();
    expect(result.session.courseName).toBeTruthy();
    expect(result.session.sessionTitle).toBeTruthy();
    expect(result.session.lecturerName).toBeTruthy();
    expect(result.session.venue).toBeTruthy();
  });

  test('returns unavailable for the explicit unavailable session', async () => {
    const service = new MockAttendanceService();

    await expect(
      service.getAttendanceSession('attendance-session-unavailable'),
    ).resolves.toEqual({
      status: 'unavailable',
    });
  });

  test('returns unavailable without throwing for an unknown session ID', async () => {
    const service = new MockAttendanceService();

    await expect(
      service.getAttendanceSession('unknown-session'),
    ).resolves.toEqual({
      status: 'unavailable',
    });
  });

  test('returns session times as valid ISO 8601 strings', async () => {
    const service = new MockAttendanceService();
    const sessionIds = [
      'attendance-session-active',
      'attendance-session-closed',
    ];

    for (const sessionId of sessionIds) {
      const result = await service.getAttendanceSession(sessionId);

      if (result.status !== 'available') {
        throw new Error(`Expected ${sessionId} to be available`);
      }

      const timeValues = [
        result.session.startTime,
        result.session.endTime,
        result.session.checkInOpensAt,
        result.session.checkInClosesAt,
        result.session.lateThreshold,
      ];

      for (const timeValue of timeValues) {
        expect(timeValue).toMatch(ISO_8601_PATTERN);
        expect(Number.isNaN(Date.parse(timeValue))).toBe(false);
      }
    }
  });
});
