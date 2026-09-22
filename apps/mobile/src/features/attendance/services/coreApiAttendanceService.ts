import type { CoreApiClient } from '../../../services/api/coreApiClient';
import type { AttendanceSession } from '../types/attendanceSession';
import type { CheckInResult, InitialCheckIn, MyAttendance, MyAttendanceResult } from '../types/myAttendance';
import type { AttendanceService, AttendanceSessionLookupResult } from './attendanceService';

function attendancePath(sessionId: string): string {
  return `/api/v1/students/me/attendance-sessions/${encodeURIComponent(sessionId)}/attendance`;
}

function checkInPath(sessionId: string): string {
  return `/api/v1/attendance-sessions/${encodeURIComponent(sessionId)}/check-in`;
}

export class CoreApiAttendanceService implements AttendanceService {
  constructor(private readonly coreApiClient: CoreApiClient) {}

  async getMyAttendance(sessionId: string): Promise<MyAttendanceResult> {
    const result = await this.coreApiClient.get<unknown>(attendancePath(sessionId));
    if (result.status !== 'ok') return { status: result.status };
    const attendance = parseMyAttendance(result.data, sessionId);
    return attendance
      ? { status: 'loaded', attendance }
      : { status: 'server-error' };
  }

  async checkIn(sessionId: string): Promise<CheckInResult> {
    const result = await this.coreApiClient.post<unknown>(checkInPath(sessionId), {});
    if (result.status !== 'ok') return result;
    if (!isRecord(result.data)) return { status: 'server-error' };
    const { status, initialCheckIn, missingRequirements } = result.data;
    if (
      !['checked_in', 'already_checked_in', 'incomplete'].includes(String(status)) ||
      !isInitialCheckIn(initialCheckIn) ||
      !Array.isArray(missingRequirements) ||
      !missingRequirements.every((item) => typeof item === 'string')
    ) return { status: 'server-error' };
    return {
      status: 'loaded',
      outcome: status as 'checked_in' | 'already_checked_in' | 'incomplete',
      initialCheckIn: initialCheckIn as InitialCheckIn | null,
      missingRequirements,
    };
  }

  async getAttendanceSession(sessionId: string): Promise<AttendanceSessionLookupResult> {
    const result = await this.getMyAttendance(sessionId);
    if (result.status !== 'loaded') return { status: 'unavailable' };
    return { status: 'available', session: toAttendanceSession(result.attendance) };
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function isDate(value: unknown): value is string {
  return typeof value === 'string' && Number.isFinite(Date.parse(value));
}

function isNullableDate(value: unknown): value is string | null {
  return value === null || isDate(value);
}

function isInitialCheckIn(value: unknown): value is InitialCheckIn | null {
  return value === null || (
    isRecord(value) &&
    (value.status === 'checked_in' || value.status === 'late_checked_in') &&
    isDate(value.checkedInAt)
  );
}

export function parseMyAttendance(value: unknown, sessionId: string): MyAttendance | null {
  if (!isRecord(value) || value.sessionId !== sessionId) return null;
  const verification = value.verification;
  const final = value.finalAttendance;
  if (
    typeof value.courseCode !== 'string' ||
    typeof value.courseName !== 'string' ||
    typeof value.sessionTitle !== 'string' ||
    typeof value.sessionType !== 'string' ||
    !['scheduled', 'active', 'closed', 'cancelled'].includes(String(value.sessionState)) ||
    !(value.cancellationReason === null || typeof value.cancellationReason === 'string') ||
    !isDate(value.scheduledStartAt) || !isDate(value.scheduledEndAt) ||
    !isNullableDate(value.checkInOpensAt) || !isNullableDate(value.checkInClosesAt) ||
    !isNullableDate(value.lateAfterAt) ||
    typeof value.requiresFaceVerification !== 'boolean' ||
    typeof value.qrEnabled !== 'boolean' || typeof value.canStartCheckIn !== 'boolean' ||
    !isRecord(verification) ||
    ![null, 'in_progress', 'checked_in', 'failed'].includes(verification.attemptStatus as null) ||
    !(verification.failureReason === null || typeof verification.failureReason === 'string') ||
    !(verification.geofenceStatus === null || typeof verification.geofenceStatus === 'string') ||
    !(verification.faceStatus === null || typeof verification.faceStatus === 'string') ||
    !(verification.livenessPassed === null || typeof verification.livenessPassed === 'boolean') ||
    !isInitialCheckIn(value.initialCheckIn) ||
    !(final === null || (isRecord(final) &&
      ['present', 'late', 'absent'].includes(String(final.status)) &&
      ['automatic', 'manual'].includes(String(final.source)) &&
      isDate(final.decidedAt)))
  ) return null;
  return value as MyAttendance;
}

export function toAttendanceSession(state: MyAttendance): AttendanceSession {
  const checkInStatus: AttendanceSession['checkInStatus'] =
    state.initialCheckIn || state.finalAttendance ? 'completed' :
      state.sessionState === 'scheduled' ? 'not_started' :
        state.canStartCheckIn ? 'open' : 'closed';
  return {
    id: state.sessionId,
    lectureId: state.sessionId,
    courseCode: state.courseCode,
    courseName: state.courseName,
    sessionTitle: state.sessionTitle,
    lecturerName: 'Lecturer',
    sessionType: state.sessionType === 'lab' || state.sessionType === 'tutorial'
      ? state.sessionType : 'lecture',
    startTime: state.scheduledStartAt,
    endTime: state.scheduledEndAt,
    venue: 'Venue TBA',
    checkInOpensAt: state.checkInOpensAt ?? state.scheduledStartAt,
    checkInClosesAt: state.checkInClosesAt ?? state.scheduledEndAt,
    lateThreshold: state.lateAfterAt ?? state.checkInClosesAt ?? state.scheduledEndAt,
    checkInStatus,
    requiresQr: state.qrEnabled,
    attemptStatus: state.verification.attemptStatus,
    finalAttendanceStatus: state.finalAttendance?.status ?? null,
  };
}
