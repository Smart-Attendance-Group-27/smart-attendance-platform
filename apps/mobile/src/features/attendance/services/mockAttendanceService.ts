import type {
  AttendanceCheckInResultLookupResult,
  AttendanceService,
  AttendanceSessionLookupResult,
} from './attendanceService';
import type { AttendanceCheckInResult } from '../types/attendanceCheckInResult';
import type { AttendanceSession } from '../types/attendanceSession';

const attendanceSessions: Readonly<Record<string, AttendanceSession>> = {
  'attendance-session-active': {
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
    requiresQr: false,
  },
  'attendance-session-closed': {
    id: 'attendance-session-closed',
    lectureId: 'lecture-cs3052-network-defence',
    courseCode: 'CS3052',
    courseName: 'Computer Security',
    sessionTitle: 'Network Defence Lab',
    lecturerName: 'Dr. R. Silva',
    sessionType: 'lab',
    startTime: '2026-07-14T08:00:00+05:30',
    endTime: '2026-07-14T10:00:00+05:30',
    venue: 'Level 2 Security Lab',
    checkInOpensAt: '2026-07-14T07:50:00+05:30',
    checkInClosesAt: '2026-07-14T08:20:00+05:30',
    lateThreshold: '2026-07-14T08:10:00+05:30',
    checkInStatus: 'closed',
    requiresQr: false,
  },
};

const checkInResults: Readonly<Record<string, AttendanceCheckInResult>> = {
  'attendance-session-active': {
    sessionId: 'attendance-session-active',
    status: 'present',
    checkInTime: '2026-07-20T10:02:00+05:30',
  },
  'attendance-session-late': {
    sessionId: 'attendance-session-late',
    status: 'late',
    checkInTime: '2026-07-20T10:18:00+05:30',
  },
};

export class MockAttendanceService implements AttendanceService {
  async getAttendanceSession(
    sessionId: string,
  ): Promise<AttendanceSessionLookupResult> {
    const session = attendanceSessions[sessionId];

    if (!session) {
      return {
        status: 'unavailable',
      };
    }

    return {
      status: 'available',
      session: { ...session },
    };
  }

  async getCheckInResult(
    sessionId: string,
  ): Promise<AttendanceCheckInResultLookupResult> {
    const result = checkInResults[sessionId];

    if (!result) {
      return {
        status: 'unavailable',
      };
    }

    return {
      status: 'available',
      result: { ...result },
    };
  }
}
