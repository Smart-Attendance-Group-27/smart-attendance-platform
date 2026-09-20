import { getMockAttendance, markMockFacePassed } from '../__fixtures__/mockAttendanceStore';
import type { AttendanceSession } from '../types/attendanceSession';
import type { CheckInResult, MyAttendanceResult } from '../types/myAttendance';
import { toAttendanceSession } from './coreApiAttendanceService';
import type { AttendanceService, AttendanceSessionLookupResult } from './attendanceService';

export class MockAttendanceService implements AttendanceService {
  async getAttendanceSession(sessionId: string): Promise<AttendanceSessionLookupResult> {
    const state = getMockAttendance(sessionId);
    if (!state) return { status: 'unavailable' };
    const session: AttendanceSession = toAttendanceSession(state);
    return { status: 'available', session };
  }

  async getMyAttendance(sessionId: string): Promise<MyAttendanceResult> {
    const attendance = getMockAttendance(sessionId);
    return attendance
      ? { status: 'loaded', attendance }
      : { status: 'not-found' };
  }

  async checkIn(sessionId: string): Promise<CheckInResult> {
    const state = getMockAttendance(sessionId);
    if (!state) return { status: 'not-found' };
    if (state.initialCheckIn) return {
      status: 'loaded', outcome: 'already_checked_in',
      initialCheckIn: state.initialCheckIn, missingRequirements: [],
    };
    if (state.sessionState !== 'active') return { status: 'conflict', errorCode: 'SESSION_NOT_ACTIVE' };
    if (state.verification.geofenceStatus !== 'passed' ||
        (state.requiresFaceVerification && state.verification.faceStatus !== 'passed')) {
      return {
        status: 'loaded', outcome: 'incomplete', initialCheckIn: null,
        missingRequirements: state.verification.geofenceStatus !== 'passed'
          ? ['geofence'] : ['face_verification'],
      };
    }
    const initialCheckIn = {
      status: 'checked_in' as const,
      checkedInAt: '2026-07-20T10:04:00+05:30',
    };
    markMockFacePassed(sessionId);
    return { status: 'loaded', outcome: 'checked_in', initialCheckIn, missingRequirements: [] };
  }
}
