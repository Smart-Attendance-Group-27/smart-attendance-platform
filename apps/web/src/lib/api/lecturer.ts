import "server-only";
import { coreBackendFetch } from "@/lib/api/coreBackend";

export type ApiLecturerCourse = {
  courseOfferingId: string;
  courseCode: string;
  courseName: string;
  departmentName: string | null;
  courseType: string | null;
  status: string;
  enrolledCount: number;
  attendanceRatePercent: number | null;
};

export type ApiLecturerTimetableEntry = {
  id: string;
  courseCode: string;
  courseName: string;
  dayOfWeek: number;
  startTime: string;
  endTime: string;
  classroomCode: string | null;
  buildingName: string | null;
};

export type ApiSessionStatus = "scheduled" | "active" | "closed" | "cancelled";

export type ApiLecturerSession = {
  id: string;
  courseOfferingId: string;
  courseCode: string;
  courseName: string;
  classroomCode: string | null;
  status: ApiSessionStatus;
  scheduledStartAt: string;
  scheduledEndAt: string;
  checkInOpensAt: string | null;
  checkInClosesAt: string | null;
  lateAfterAt: string | null;
  activatedAt: string | null;
  closedAt: string | null;
  requiresFaceVerification: boolean;
  requiresGeofence: boolean;
  requiresQr: boolean;
  enrolledCount: number;
  presentCount: number;
  lateCount: number;
  pendingReviewCount: number;
};

export type ApiSessionStudent = {
  studentId: string;
  registrationNumber: string;
  fullName: string;
  verificationStatus: string | null;
  geofenceStatus: string | null;
  faceStatus: string | null;
  faceSimilarityScore: number | null;
  faceLivenessPassed: boolean | null;
  qrStatus: string | null;
  attendanceStatus: string | null;
  reviewStatus: string | null;
  checkedInAt: string | null;
};

export type ApiManualReviewDecision = "approve" | "reject" | "retry" | "escalate";

export type ApiManualReviewQueueItem = {
  verificationAttemptId: string;
  sessionId: string;
  courseCode: string;
  courseName: string;
  classroomCode: string | null;
  scheduledStartAt: string;
  studentId: string;
  registrationNumber: string;
  fullName: string;
  failureReason: string | null;
  startedAt: string | null;
  completedAt: string | null;
  geofenceStatus: string | null;
  geofenceFailureReason: string | null;
  faceStatus: string | null;
  faceSimilarityScore: number | null;
  faceLivenessPassed: boolean | null;
  qrStatus: string | null;
  reviewStatus: string;
  decisionReason: string | null;
  reviewedAt: string | null;
};

export type ApiLecturerDashboardOverview = {
  activeCourseCount: number;
  upcomingSessionCount: number;
  todaySessionCount: number;
  averageAttendanceRatePercent: number | null;
  pendingReviewCount: number;
};

export type ApiCourseSessionReport = {
  sessionId: string;
  scheduledStartAt: string;
  status: ApiSessionStatus;
  enrolledCount: number;
  presentCount: number;
  lateCount: number;
  absentCount: number;
  pendingReviewCount: number;
};

export type ApiWeeklyTrendPoint = {
  label: string;
  attendanceRate: number;
};

export type ApiAtRiskStudent = {
  studentId: string;
  registrationNumber: string;
  fullName: string;
  courseCode: string;
  attendanceRatePercent: number;
  lateCount: number;
  lastAttendedAt: string | null;
};

export function getLecturerCourses(): Promise<ApiLecturerCourse[]> {
  return coreBackendFetch("/api/v1/lecturers/me/courses");
}

export function getLecturerTimetable(): Promise<ApiLecturerTimetableEntry[]> {
  return coreBackendFetch("/api/v1/lecturers/me/timetable");
}

export function getLecturerSessions(): Promise<ApiLecturerSession[]> {
  return coreBackendFetch("/api/v1/lecturers/me/attendance-sessions");
}

export function getLecturerSessionDetail(sessionId: string): Promise<ApiLecturerSession> {
  return coreBackendFetch(`/api/v1/lecturers/me/attendance-sessions/${sessionId}`);
}

export function getLecturerSessionStudents(sessionId: string): Promise<ApiSessionStudent[]> {
  return coreBackendFetch(`/api/v1/lecturers/me/attendance-sessions/${sessionId}/students`);
}

export function activateLecturerSession(sessionId: string): Promise<ApiLecturerSession> {
  return coreBackendFetch(`/api/v1/lecturers/me/attendance-sessions/${sessionId}/activate`, {
    method: "POST",
  });
}

export function closeLecturerSession(sessionId: string): Promise<ApiLecturerSession> {
  return coreBackendFetch(`/api/v1/lecturers/me/attendance-sessions/${sessionId}/close`, {
    method: "POST",
  });
}

export function getManualReviewQueue(): Promise<ApiManualReviewQueueItem[]> {
  return coreBackendFetch("/api/v1/lecturers/me/manual-reviews");
}

export function postManualReviewDecision(
  verificationAttemptId: string,
  decision: ApiManualReviewDecision,
  reason: string | undefined,
): Promise<ApiManualReviewQueueItem> {
  return coreBackendFetch(`/api/v1/lecturers/me/manual-reviews/${verificationAttemptId}/decision`, {
    method: "POST",
    body: { decision, reason },
  });
}

export function getLecturerDashboardOverview(): Promise<ApiLecturerDashboardOverview> {
  return coreBackendFetch("/api/v1/lecturers/me/dashboard-overview");
}

export function getCourseSessionReport(courseOfferingId: string): Promise<ApiCourseSessionReport[]> {
  return coreBackendFetch(`/api/v1/lecturers/me/reports/courses/${courseOfferingId}`);
}

export function getLecturerAttendanceTrend(): Promise<ApiWeeklyTrendPoint[]> {
  return coreBackendFetch("/api/v1/lecturers/me/reports/attendance-trend");
}

export function getLecturerAtRiskStudents(): Promise<ApiAtRiskStudent[]> {
  return coreBackendFetch("/api/v1/lecturers/me/reports/at-risk-students");
}
