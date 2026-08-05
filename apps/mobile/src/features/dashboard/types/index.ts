export type Lecture = {
  id: string;
  courseId: string;
  courseCode: string;
  courseName: string;
  startTime: string;
  endTime: string;
  venue: string;
};

export type AttendanceSession = {
  id: string;
  lectureId: string;
  courseCode: string;
  courseName: string;
  startTime: string;
  endTime: string;
  lateThreshold: string;
  checkInStatus: 'not_started' | 'open' | 'closed';
};