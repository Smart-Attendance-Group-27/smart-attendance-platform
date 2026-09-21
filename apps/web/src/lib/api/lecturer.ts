import "server-only";
import { coreBackendFetch } from "@/lib/api/coreBackend";
import { isWebMockMode } from "@/lib/api/mode";
import {
  mockLecturerDashboardOverview,
  mockLecturerAttendanceTrend,
  mockLecturerQrBatches,
  mockLecturerSessions,
  mockLecturerStudents,
  mockLecturerTimetable,
} from "@/mocks/fixtures/lecturerLive";
import type { LecturerQrBatch } from "@/types/lecturer";

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

export type ApiFinalizationSummary = {
  enrolledCount: number;
  presentCount: number;
  lateCount: number;
  absentCount: number;
  keptManualCount: number;
  reconciledCount: number;
  deactivatedQrBatchCount: number;
  finalizedAt: string;
};

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
  checkedInCount: number;
  lateCheckedInCount: number;
  notCheckedInCount: number;
  failedVerificationCount: number;
  absentCount: number;
  manualCount: number;
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
  failureReason: string | null;
  initialCheckInStatus: "checked_in" | "late_checked_in" | null;
  qrRequiredCount: number | null;
  qrPassedCount: number | null;
  recordSource: "automatic" | "manual" | null;
  manualReason: string | null;
  recordUpdatedAt: string | null;
};

export type ApiManualAttendanceStatus = "present" | "late" | "absent";

export type ApiManualAttendanceResponse = {
  sessionId: string;
  studentId: string;
  status: ApiManualAttendanceStatus;
  source: "manual";
  reason: string;
  recordedBy: string;
  updatedAt: string;
};

export type ApiManualReviewDecisionRequest =
  | { decision: "approve"; attendanceStatus: "present" | "late"; reason: string }
  | { decision: "reject"; reason: string };

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
  if (isWebMockMode()) return Promise.resolve(mockLecturerTimetable);
  return coreBackendFetch("/api/v1/lecturers/me/timetable");
}

export type ApiCreateSessionRequest = {
  timetableEntryId: string;
  sessionTitle: string;
  sessionType?: string;
  scheduledStartAt: string;
  scheduledEndAt: string;
  checkInOpensAt?: string;
  checkInClosesAt?: string;
  lateAfterAt?: string;
  requiresFaceVerification?: boolean;
  requiresGeofence?: boolean;
  requiresQr?: boolean;
};

export function getLecturerSessions(): Promise<ApiLecturerSession[]> {
  if (isWebMockMode()) return Promise.resolve(mockLecturerSessions);
  return coreBackendFetch("/api/v1/lecturers/me/attendance-sessions");
}

export function createLecturerSession(body: ApiCreateSessionRequest): Promise<ApiLecturerSession> {
  return coreBackendFetch("/api/v1/lecturers/me/attendance-sessions", {
    method: "POST",
    body,
  });
}

export function getLecturerSessionDetail(sessionId: string): Promise<ApiLecturerSession> {
  if (isWebMockMode()) {
    const session = mockLecturerSessions.find((item) => item.id === sessionId);
    return session ? Promise.resolve(session) : Promise.reject(new Error("Session not found"));
  }
  return coreBackendFetch(`/api/v1/lecturers/me/attendance-sessions/${sessionId}`);
}

export function getLecturerSessionStudents(sessionId: string): Promise<ApiSessionStudent[]> {
  if (isWebMockMode()) return Promise.resolve(mockLecturerStudents[sessionId] ?? []);
  return coreBackendFetch(`/api/v1/lecturers/me/attendance-sessions/${sessionId}/students`);
}

export function putManualAttendance(
  sessionId: string,
  studentId: string,
  body: { status: ApiManualAttendanceStatus; reason: string },
): Promise<ApiManualAttendanceResponse> {
  return coreBackendFetch(
    `/api/v1/lecturers/me/attendance-sessions/${encodeURIComponent(sessionId)}/students/${encodeURIComponent(studentId)}/attendance`,
    { method: "PUT", body },
  );
}

export function getLecturerQrBatches(sessionId: string): Promise<LecturerQrBatch[]> {
  if (isWebMockMode()) return Promise.resolve(mockLecturerQrBatches[sessionId] ?? []);
  return coreBackendFetch(`/api/v1/lecturers/me/attendance-sessions/${encodeURIComponent(sessionId)}/qr-batches`);
}

export function activateLecturerSession(sessionId: string): Promise<ApiLecturerSession> {
  return coreBackendFetch(`/api/v1/lecturers/me/attendance-sessions/${sessionId}/activate`, {
    method: "POST",
  });
}

export function closeLecturerSession(sessionId: string): Promise<ApiLecturerSession & { finalization: ApiFinalizationSummary | null }> {
  return coreBackendFetch(`/api/v1/lecturers/me/attendance-sessions/${encodeURIComponent(sessionId)}/close`, {
    method: "POST",
  });
}

export function cancelLecturerSession(sessionId: string, reason: string): Promise<ApiLecturerSession> {
  return coreBackendFetch(`/api/v1/lecturers/me/attendance-sessions/${encodeURIComponent(sessionId)}/cancel`, {
    method: "POST",
    body: { reason },
  });
}

export function getManualReviewQueue(): Promise<ApiManualReviewQueueItem[]> {
  return coreBackendFetch("/api/v1/lecturers/me/manual-reviews");
}

export function postManualReviewDecision(
  verificationAttemptId: string,
  body: ApiManualReviewDecisionRequest,
): Promise<ApiManualReviewQueueItem> {
  return coreBackendFetch(`/api/v1/lecturers/me/manual-reviews/${verificationAttemptId}/decision`, {
    method: "POST",
    body,
  });
}

export function getLecturerDashboardOverview(): Promise<ApiLecturerDashboardOverview> {
  if (isWebMockMode()) return Promise.resolve(mockLecturerDashboardOverview);
  return coreBackendFetch("/api/v1/lecturers/me/dashboard-overview");
}

export function getCourseSessionReport(courseOfferingId: string): Promise<ApiCourseSessionReport[]> {
  return coreBackendFetch(`/api/v1/lecturers/me/reports/courses/${courseOfferingId}`);
}

export function getLecturerAttendanceTrend(): Promise<ApiWeeklyTrendPoint[]> {
  if (isWebMockMode()) return Promise.resolve(mockLecturerAttendanceTrend);
  return coreBackendFetch("/api/v1/lecturers/me/reports/attendance-trend");
}

export function getLecturerAtRiskStudents(): Promise<ApiAtRiskStudent[]> {
  return coreBackendFetch("/api/v1/lecturers/me/reports/at-risk-students");
}
