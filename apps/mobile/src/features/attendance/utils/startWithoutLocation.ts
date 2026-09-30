import type { AttendanceService } from '../services/attendanceService';

export type StartWithoutLocationDestination = 'face' | 'progress';

// Opens the attempt after a geofence waiver and says where to go next. Any
// failure lands on the progress screen, which shows the real state and a retry.
export async function startWithoutLocation(
  attendanceService: AttendanceService,
  sessionId: string,
): Promise<StartWithoutLocationDestination> {
  try {
    const result = await attendanceService.startVerificationWithoutLocation(sessionId);
    return result.status === 'started' && !result.initialCheckIn ? 'face' : 'progress';
  } catch {
    return 'progress';
  }
}
