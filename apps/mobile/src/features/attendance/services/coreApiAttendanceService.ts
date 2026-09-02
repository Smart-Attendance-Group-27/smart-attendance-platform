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

function completeCheckInPath(sessionId: string): string {
  return `/api/v1/attendance-sessions/${encodeURIComponent(sessionId)}/complete-check-in`;
}

type ActiveAttendanceSessionResponse = Partial<
  Record<keyof ActiveAttendanceSession, unknown>
>;

type CompleteCheckInResponse = {
  readonly status?: unknown;
  readonly attendanceStatus?: unknown;
  readonly checkedInAt?: unknown;
};

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
    // Asks the backend to finalize check-in: it re-checks, server-side, that
    // every verification the session actually requires (geofence, face, QR)
    // has genuinely passed, then writes the real attendance record. This
    // used to be fabricated client-side from the phone's clock — the
    // backend is now the sole source of truth for present/late.
    const result = await this.coreApiClient.post<unknown>(
      completeCheckInPath(sessionId),
      {},
    );

    if (result.status !== 'ok') {
      return { status: 'unavailable' };
    }

    const outcome = toCompleteCheckInOutcome(sessionId, result.data);
    return outcome ? { status: 'available', result: outcome } : { status: 'unavailable' };
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

function toCompleteCheckInOutcome(
  sessionId: string,
  value: unknown,
): AttendanceCheckInResult | null {
  if (!value || typeof value !== 'object') {
    return null;
  }

  const response = value as CompleteCheckInResponse;
  if (
    response.status !== 'completed' ||
    (response.attendanceStatus !== 'present' && response.attendanceStatus !== 'late') ||
    typeof response.checkedInAt !== 'string' ||
    !response.checkedInAt.trim()
  ) {
    return null;
  }

  return {
    sessionId,
    status: response.attendanceStatus,
    checkInTime: response.checkedInAt,
  };
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
    checkInStatus: 'open',
    requiresQr: session.requiresQr,
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
