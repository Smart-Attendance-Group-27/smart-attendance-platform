import type { AttendanceSession } from '../types/attendanceSession';
import type { AttendanceCheckInResult } from '../types/attendanceCheckInResult';

export type AttendanceSessionLookupResult =
  | {
      status: 'available';
      session: AttendanceSession;
    }
  | {
      status: 'unavailable';
    };

export type AttendanceCheckInResultLookupResult =
  | {
      status: 'available';
      result: AttendanceCheckInResult;
    }
  | {
      status: 'unavailable';
    };

export interface AttendanceService {
  getAttendanceSession(
    sessionId: string,
  ): Promise<AttendanceSessionLookupResult>;

  getCheckInResult(
    sessionId: string,
  ): Promise<AttendanceCheckInResultLookupResult>;
}
