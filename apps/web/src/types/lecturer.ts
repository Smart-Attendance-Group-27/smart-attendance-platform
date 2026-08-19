// Field names follow the existing backend schema (database/smart_attendance_db_clean.sql)
// where a matching table/column already exists, so a future services/lecturer.ts can map
// API responses onto these types without renaming anything downstream.

export type SessionStatus = "scheduled" | "in_progress" | "closed" | "cancelled";

export type TodayLecture = {
  sessionId: string;
  courseCode: string;
  courseName: string;
  timeRange: string;
  room: string;
  checkInWindow: string;
  presentCount: number;
  enrolledCount: number;
  status: SessionStatus;
};

export type AttentionItem = {
  id: string;
  time: string;
  title: string;
  detail: string;
  severity: "danger" | "warning" | "info";
};

export type RecentActivityItem = {
  id: string;
  time: string;
  title: string;
  detail: string;
  tag: "qr" | "success" | "info";
};

export type WeeklyTrendPoint = {
  label: string;
  attendanceRate: number;
};

export type LecturerOverview = {
  summary: {
    activeLectures: number;
    checkInWindowsOpen: number;
    studentsCheckedIn: number;
    pendingReview: number;
    pendingReviewNeedingAction: number;
    attendanceRatePercent: number;
    attendanceRateDeltaPercent: number;
  };
  todayLectures: TodayLecture[];
  attentionItems: AttentionItem[];
  weeklyTrend: WeeklyTrendPoint[];
  recentActivity: RecentActivityItem[];
};

export type CourseStatus = "active" | "correction_needed";

export type LecturerCourse = {
  courseId: string;
  courseCode: string;
  courseName: string;
  scheduleSummary: string;
  lecturerName: string;
  enrolledCount: number;
  attendanceRatePercent: number;
  status: CourseStatus;
};

export type TimetableEntry = {
  id: string;
  day: string;
  timeRange: string;
  courseCode: string;
  courseName: string;
  room: string;
  source: string;
};

// One of the lecturer's own academic.timetable_entries rows — the source a
// new session is instantiated from (see app/actions/sessions.ts).
export type TimetableOption = {
  id: string;
  label: string;
};

export type SourceSyncItem = {
  id: string;
  time: string;
  title: string;
  detail: string;
  status: "current" | "review";
};

export type LecturerCoursesData = {
  semesterLabel: string;
  courses: LecturerCourse[];
  timetable: TimetableEntry[];
  sourceStatus: SourceSyncItem[];
};

export type VerificationOutcome = "present" | "failed" | "late" | "not_required" | "not_submitted" | "not_participated" | "participated";

export type SessionStudentRow = {
  studentId: string;
  studentIndex: string;
  fullName: string;
  // Students verify their face once, at the start of the lecture — there is
  // no lecturer-triggered second/"additional" face check.
  initialFaceCheck: VerificationOutcome;
  qrVerification: VerificationOutcome;
  finalStatus: "present" | "late" | "absent" | "pending_review";
  time: string;
};

export type SessionDetail = {
  sessionId: string;
  courseCode: string;
  courseName: string;
  room: string;
  status: SessionStatus;
  startedAtLabel: string;
  checkInWindow: string;
  lateThreshold: string;
  lecturerName: string;
  summary: {
    presentCount: number;
    presentPercent: number;
    lateCount: number;
    latePercent: number;
    pendingReviewCount: number;
    notVerifiedCount: number;
    notVerifiedPercent: number;
  };
  students: SessionStudentRow[];
};

export type ReviewIssueType =
  | "low_confidence_face_match"
  | "borderline_geofence"
  | "expired_qr_submission"
  | "duplicate_submission";

export type ReviewCaseStatus = "pending" | "information";

export type ReviewCase = {
  caseId: string;
  studentId: string;
  studentIndex: string;
  studentName: string;
  studentProgramme: string;
  courseCode: string;
  issueType: ReviewIssueType;
  issueLabel: string;
  faceScorePercent: number;
  geofenceResult: "within_radius" | "boundary" | "outside_radius";
  time: string;
  status: ReviewCaseStatus;
  livenessPassed: boolean;
  geofenceDistanceMeters: number;
  qrEventLabel: string;
  reviewReason: string;
};

export type AtRiskStudent = {
  studentId: string;
  studentIndex: string;
  studentName: string;
  courseCode: string;
  attendanceRatePercent: number;
  lateCount: number;
  lastAttendedLabel: string;
  riskLevel: "high" | "medium";
};

export type LecturerReportsData = {
  summary: {
    overallAttendancePercent: number;
    sessionsCompleted: number;
    averageLateRatePercent: number;
    averageLateRateDeltaPercent: number;
    studentsAtRiskCount: number;
  };
  attendanceTrend: WeeklyTrendPoint[];
  attendanceByCourse: { courseCode: string; attendanceRatePercent: number }[];
  atRiskStudents: AtRiskStudent[];
};
