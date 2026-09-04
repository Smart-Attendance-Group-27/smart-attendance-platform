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
    // Completes the START-OF-LECTURE check-in. The backend re-checks,
    // server-side, that the checks this session requires at the start have
    // genuinely passed, then records the provisional CHECKED_IN state.
    //
    // It deliberately does NOT decide final attendance: the lecturer may
    // still run QR verifications, and present/late is settled once, when the
    // session is finalized. A `present`/`late` answer here only happens when
    // the session was already finalized before this call.
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

  if (typeof response.checkedInAt !== 'string' || !response.checkedInAt.trim()) {
    // Every successful outcome carries the moment check-in completed.
    // "incomplete" and "failed" do not, and are reported as unavailable.
    return null;
  }

  if (response.status === 'checked_in') {
    return {
      sessionId,
      status: 'checked_in',
      checkInTime: response.checkedInAt,
    };
  }

  // The session was already finalized, so report the real final status
  // rather than a check-in that has since been superseded.
  if (
    response.status === 'completed' &&
    (response.attendanceStatus === 'present' || response.attendanceStatus === 'late')
  ) {
    return {
      sessionId,
      status: response.attendanceStatus,
      checkInTime: response.checkedInAt,
    };
  }

  return null;
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
