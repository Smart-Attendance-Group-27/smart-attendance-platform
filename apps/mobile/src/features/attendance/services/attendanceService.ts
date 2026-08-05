import type { AttendanceSession } from '../types/attendanceSession';

export type AttendanceSessionLookupResult =
  | {
      status: 'available';
      session: AttendanceSession;
    }
  | {
      status: 'unavailable';
    };

export interface AttendanceService {
  getAttendanceSession(
    sessionId: string,
  ): Promise<AttendanceSessionLookupResult>;
}
