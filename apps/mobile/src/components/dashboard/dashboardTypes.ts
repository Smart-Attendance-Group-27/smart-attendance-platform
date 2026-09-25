export type CourseSummary = {
  code: string;
  title: string;
  lecturer: string;
  // null until the course has at least one closed session.
  attendancePercentage: number | null;
  upcomingSessions: number;
  color: string;
};

export type UpcomingAttendance = {
  id: string;
  day: string;
  month: string;
  course: string;
  time: string;
  location: string;
};
