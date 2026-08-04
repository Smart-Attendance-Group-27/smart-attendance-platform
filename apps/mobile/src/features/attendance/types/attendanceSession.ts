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
};
