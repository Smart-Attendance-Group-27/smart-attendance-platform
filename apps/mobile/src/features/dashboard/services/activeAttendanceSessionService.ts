import type { ActiveAttendanceSessionsResult } from '../types/activeAttendanceSession';

export interface ActiveAttendanceSessionService {
  listMyActiveSessions(): Promise<ActiveAttendanceSessionsResult>;
}
