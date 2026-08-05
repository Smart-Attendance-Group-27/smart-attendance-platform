import { describe, expect, test } from '@jest/globals';

import type { AttendanceSession } from '../types/attendanceSession';
import {
  formatAttendanceDate,
  formatAttendanceSession,
  formatAttendanceTime,
  formatAttendanceTimeRange,
} from '../utils/formatAttendanceSession';

const fixedFormatting = {
  locale: 'en-GB',
  timeZone: 'Asia/Colombo',
};

const session: AttendanceSession = {
  id: 'attendance-session-active',
  lectureId: 'lecture-cs3203-architecture-review',
  courseCode: 'CS3203',
  courseName: 'Software Engineering Project',
  sessionTitle: 'Architecture Review Lecture',
  lecturerName: 'Dr. N. Perera',
  sessionType: 'lecture',
  startTime: '2026-07-20T10:00:00+05:30',
  endTime: '2026-07-20T12:00:00+05:30',
  venue: 'Level 3 Lab',
  checkInOpensAt: '2026-07-20T09:50:00+05:30',
  checkInClosesAt: '2026-07-20T10:20:00+05:30',
  lateThreshold: '2026-07-20T10:10:00+05:30',
  checkInStatus: 'open',
};

describe('attendance session formatting', () => {
  test('formats ISO date and time values in a supplied timezone', () => {
    expect(
      formatAttendanceDate(session.startTime, fixedFormatting),
    ).toBe('Monday, 20 July 2026');
    expect(
      formatAttendanceTime(session.startTime, fixedFormatting),
    ).toBe('10:00');
    expect(
      formatAttendanceTimeRange(
        session.startTime,
        session.endTime,
        fixedFormatting,
      ),
    ).toBe('10:00–12:00');
  });

  test('builds a presentation-only view without changing the session', () => {
    const originalSession = { ...session };

    expect(formatAttendanceSession(session, fixedFormatting)).toEqual({
      date: 'Monday, 20 July 2026',
      scheduledTime: '10:00–12:00',
      checkInWindow: '09:50–10:20',
      lateThreshold: '10:10',
      sessionType: 'Lecture',
    });
    expect(session).toEqual(originalSession);
  });

  test('returns safe fallback text for invalid date values', () => {
    expect(formatAttendanceDate('invalid', fixedFormatting)).toBe(
      'Date unavailable',
    );
    expect(formatAttendanceTime('invalid', fixedFormatting)).toBe(
      'Time unavailable',
    );
    expect(
      formatAttendanceTimeRange(
        session.startTime,
        'invalid',
        fixedFormatting,
      ),
    ).toBe('Time unavailable');
  });
});
