import { myAttendanceFixtures } from '../../attendance/__fixtures__/myAttendance';
import { getMockAttendance } from '../../attendance/__fixtures__/mockAttendanceStore';
import type { MyAttendance } from '../../attendance/types/myAttendance';
import type { ActiveAttendanceSession } from '../types/activeAttendanceSession';
import type { ActiveAttendanceSessionService } from './activeAttendanceSessionService';

function toActiveSession(state: MyAttendance): ActiveAttendanceSession {
  return {
    id: state.sessionId,
    courseCode: state.courseCode,
    courseName: state.courseName,
    sessionTitle: state.sessionTitle,
    sessionType: state.sessionType,
    lecturerNames: 'Lecturer',
    scheduledStartAt: state.scheduledStartAt,
    scheduledEndAt: state.scheduledEndAt,
    checkInOpensAt: state.checkInOpensAt ?? state.scheduledStartAt,
    checkInClosesAt: state.checkInClosesAt ?? state.scheduledEndAt,
    lateAfterAt: state.lateAfterAt,
    venue: 'Venue TBA',
    requiresFaceVerification: state.requiresFaceVerification,
    requiresGeofence: true,
    requiresQr: state.qrEnabled,
    attemptStatus: state.verification.attemptStatus,
    initialCheckInStatus: state.initialCheckIn?.status ?? null,
    checkedInAt: state.initialCheckIn?.checkedInAt ?? null,
    finalAttendanceStatus: state.finalAttendance?.status ?? null,
  };
}

export class MockActiveAttendanceSessionService implements ActiveAttendanceSessionService {
  async listMyActiveSessions() {
    const sessions = ['attendance-session-active', 'attendance-session-checked-in']
      .map((id) => getMockAttendance(id) ?? myAttendanceFixtures[id])
      .filter((state): state is MyAttendance => Boolean(state))
      .map(toActiveSession);
    return { status: 'loaded' as const, sessions };
  }
}
