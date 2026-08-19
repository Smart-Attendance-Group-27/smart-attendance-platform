export type AttendanceSessionType =
  | 'lecture'
  | 'lab'
  | 'tutorial';

export type AttendanceCheckInStatus =
  | 'not_started'
  | 'open'
  | 'closed';

export type AttendanceSession = {
  id: string;
  lectureId: string;
  courseCode: string;
  courseName: string;
  sessionTitle: string;
  lecturerName: string;
  sessionType: AttendanceSessionType;
  startTime: string;
  endTime: string;
  venue: string;
  checkInOpensAt: string;
  checkInClosesAt: string;
  lateThreshold: string;
  checkInStatus: AttendanceCheckInStatus;
  // Whether the lecturer configured a QR verification step for this session
  // (attendance_session.sessions.requires_qr) — controls whether the
  // check-in wizard routes through the QR scanner after face verification.
  requiresQr: boolean;
};
