import type { AttendanceSession } from '../types/attendanceSession';
import type {
  CheckInResult,
  MyAttendanceResult,
  StartVerificationResult,
} from '../types/myAttendance';

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
  // Opens the attempt without a location reading. Only accepted by the
  // server once the lecturer has waived geofence for the session.
  startVerificationWithoutLocation(sessionId: string): Promise<StartVerificationResult>;
}
