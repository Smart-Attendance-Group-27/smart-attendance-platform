import type { CoreApiClient } from '../../../services/api/coreApiClient';
import type {
  ActiveAttendanceSession,
  ActiveAttendanceSessionsResult,
} from '../types/activeAttendanceSession';
import type { ActiveAttendanceSessionService } from './activeAttendanceSessionService';

const activeSessionsPath =
  '/api/v1/students/me/attendance-sessions/active';

type ActiveAttendanceSessionResponse = Partial<
  Record<keyof ActiveAttendanceSession, unknown>
>;

export class CoreApiActiveAttendanceSessionService
  implements ActiveAttendanceSessionService
{
  constructor(private readonly coreApiClient: CoreApiClient) {}

  async listMyActiveSessions(): Promise<ActiveAttendanceSessionsResult> {
    const result = await this.coreApiClient.get<unknown>(activeSessionsPath);

    if (result.status !== 'ok') {
      return { status: result.status };
    }

    if (!Array.isArray(result.data)) {
      return { status: 'server-error' };
    }

    const sessions = result.data.map(toActiveAttendanceSession);
    if (sessions.some((session) => session === null)) {
      return { status: 'server-error' };
    }

    return {
      status: 'loaded',
      sessions: sessions as ActiveAttendanceSession[],
    };
  }
}

function toActiveAttendanceSession(
  value: unknown,
): ActiveAttendanceSession | null {
  if (!isResponse(value)) {
    return null;
  }

  return value;
}

function isResponse(value: unknown): value is ActiveAttendanceSession {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const response = value as ActiveAttendanceSessionResponse;
  return (
    typeof response.id === 'string' &&
    typeof response.courseCode === 'string' &&
    typeof response.courseName === 'string' &&
    typeof response.sessionTitle === 'string' &&
    typeof response.sessionType === 'string' &&
    (response.lecturerNames === undefined ||
      response.lecturerNames === null ||
      typeof response.lecturerNames === 'string') &&
    isDateTime(response.scheduledStartAt) &&
    isDateTime(response.scheduledEndAt) &&
    isDateTime(response.checkInOpensAt) &&
    isDateTime(response.checkInClosesAt) &&
    (response.lateAfterAt === null || isDateTime(response.lateAfterAt)) &&
    (response.venue === null || typeof response.venue === 'string') &&
    typeof response.requiresFaceVerification === 'boolean' &&
    typeof response.requiresGeofence === 'boolean' &&
    typeof response.requiresQr === 'boolean' &&
    (response.attemptStatus === null ||
      response.attemptStatus === 'in_progress' ||
      response.attemptStatus === 'checked_in' ||
      response.attemptStatus === 'failed') &&
    (response.initialCheckInStatus === null ||
      response.initialCheckInStatus === 'checked_in' ||
      response.initialCheckInStatus === 'late_checked_in') &&
    (response.checkedInAt === null || isDateTime(response.checkedInAt)) &&
    (response.finalAttendanceStatus === null ||
      response.finalAttendanceStatus === 'present' ||
      response.finalAttendanceStatus === 'late' ||
      response.finalAttendanceStatus === 'absent')
  );
}

function isDateTime(value: unknown): value is string {
  return typeof value === 'string' && Number.isFinite(Date.parse(value));
}
