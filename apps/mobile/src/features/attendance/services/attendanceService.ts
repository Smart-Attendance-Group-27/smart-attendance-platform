import type { AttendanceSession } from '../types/attendanceSession';
import type { CheckInResult, MyAttendanceResult } from '../types/myAttendance';

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

  getMyAttendance(sessionId: string): Promise<MyAttendanceResult>;
  checkIn(sessionId: string): Promise<CheckInResult>;
}
