import type { CoreApiClient } from '../../../services/api/coreApiClient';
import type { ActiveAttendanceSession } from '../../dashboard/types/activeAttendanceSession';
import type { AttendanceCheckInResult } from '../types/attendanceCheckInResult';
import type { AttendanceSession } from '../types/attendanceSession';
import type {
  AttendanceCheckInResultLookupResult,
  AttendanceService,
  AttendanceSessionLookupResult,
} from './attendanceService';

const activeSessionsPath =
  '/api/v1/students/me/attendance-sessions/active';

type ActiveAttendanceSessionResponse = Partial<
  Record<keyof ActiveAttendanceSession, unknown>
>;

export class CoreApiAttendanceService implements AttendanceService {
  constructor(private readonly coreApiClient: CoreApiClient) {}

  async getAttendanceSession(
    sessionId: string,
  ): Promise<AttendanceSessionLookupResult> {
    const sessions = await this.loadActiveSessions();
    const session = sessions.find((item) => item.id === sessionId);

    if (!session) {
      return { status: 'unavailable' };
    }

    return {
      status: 'available',
      session: toAttendanceSession(session),
    };
  }

  async getCheckInResult(
    sessionId: string,
  ): Promise<AttendanceCheckInResultLookupResult> {
    const lookup = await this.getAttendanceSession(sessionId);
    if (lookup.status !== 'available') {
      return { status: 'unavailable' };
    }

    const result: AttendanceCheckInResult = {
      sessionId,
      status:
        Date.now() <= Date.parse(lookup.session.lateThreshold)
          ? 'present'
          : 'late',
      checkInTime: new Date().toISOString(),
    };

    return { status: 'available', result };
  }

  private async loadActiveSessions(): Promise<ActiveAttendanceSession[]> {
    const result = await this.coreApiClient.get<unknown>(activeSessionsPath);
    if (result.status !== 'ok' || !Array.isArray(result.data)) {
      return [];
    }

    const sessions = result.data.map(toActiveAttendanceSession);
    return sessions.filter(
      (session): session is ActiveAttendanceSession => session !== null,
    );
  }
}

function toActiveAttendanceSession(
  value: unknown,
): ActiveAttendanceSession | null {
  if (!value || typeof value !== 'object') {
    return null;
  }

  const response = value as ActiveAttendanceSessionResponse;
  if (
    typeof response.id !== 'string' ||
    typeof response.courseCode !== 'string' ||
    typeof response.courseName !== 'string' ||
    typeof response.sessionTitle !== 'string' ||
    typeof response.sessionType !== 'string' ||
    (response.lecturerNames !== undefined &&
      response.lecturerNames !== null &&
      typeof response.lecturerNames !== 'string') ||
    typeof response.scheduledStartAt !== 'string' ||
    typeof response.scheduledEndAt !== 'string' ||
    typeof response.checkInOpensAt !== 'string' ||
    typeof response.checkInClosesAt !== 'string' ||
    (response.checkInStatus !== 'not_started' &&
      response.checkInStatus !== 'open' &&
      response.checkInStatus !== 'closed') ||
    (response.lateAfterAt !== null &&
      typeof response.lateAfterAt !== 'string') ||
    (response.venue !== null && typeof response.venue !== 'string') ||
    typeof response.requiresFaceVerification !== 'boolean' ||
    typeof response.requiresGeofence !== 'boolean' ||
    typeof response.requiresQr !== 'boolean'
  ) {
    return null;
  }

  return response as ActiveAttendanceSession;
}

function toAttendanceSession(
  session: ActiveAttendanceSession,
): AttendanceSession {
  return {
    id: session.id,
    lectureId: session.id,
    courseCode: session.courseCode,
    courseName: session.courseName,
    sessionTitle: session.sessionTitle,
    lecturerName: session.lecturerNames ?? 'Lecturer not assigned',
    sessionType: toAttendanceSessionType(session.sessionType),
    startTime: session.scheduledStartAt,
    endTime: session.scheduledEndAt,
    venue: session.venue ?? 'Venue TBA',
    checkInOpensAt: session.checkInOpensAt,
    checkInClosesAt: session.checkInClosesAt,
    lateThreshold: session.lateAfterAt ?? session.checkInClosesAt,
    checkInStatus: session.checkInStatus,
  };
}

function toAttendanceSessionType(
  value: string,
): AttendanceSession['sessionType'] {
  if (value === 'lab' || value === 'tutorial') {
    return value;
  }
  return 'lecture';
}
