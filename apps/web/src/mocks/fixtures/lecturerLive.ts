import type {
  ApiLecturerDashboardOverview,
  ApiFinalizationSummary,
  ApiLecturerSession,
  ApiLecturerTimetableEntry,
  ApiSessionStudent,
  ApiWeeklyTrendPoint,
} from "@/lib/api/lecturer";
import type { LecturerQrBatch } from "@/types/lecturer";

const time = (minutesFromNow: number) => new Date(Date.now() + minutesFromNow * 60_000).toISOString();

const activeSession: ApiLecturerSession = {
  id: "mock-live-session", courseOfferingId: "mock-course", courseCode: "CS3203",
  courseName: "Software Engineering Project", classroomCode: "LT-301", status: "active",
  scheduledStartAt: time(-10), scheduledEndAt: time(80),
  checkInOpensAt: time(-15), checkInClosesAt: time(25), lateAfterAt: time(5),
  activatedAt: time(-10), closedAt: null,
  cancelledAt: null, cancellationReason: null,
  requiresFaceVerification: true, requiresGeofence: true, requiresQr: true,
  enrolledCount: 5, presentCount: 1, lateCount: 0, pendingReviewCount: 1,
  checkedInCount: 1, lateCheckedInCount: 1, notCheckedInCount: 2,
  failedVerificationCount: 1, absentCount: 0, manualCount: 1,
};

export const mockLecturerSessions: ApiLecturerSession[] = [
  activeSession,
  {
    ...activeSession, id: "mock-closed-session", courseCode: "CS2101",
    courseName: "Introduction to Programming", status: "closed",
    scheduledStartAt: time(-180), scheduledEndAt: time(-90),
    checkInOpensAt: time(-195), checkInClosesAt: time(-150),
    lateAfterAt: time(-165), activatedAt: time(-180), closedAt: time(-90),
    requiresQr: false, enrolledCount: 4, presentCount: 2, lateCount: 1,
    absentCount: 1, checkedInCount: 2, lateCheckedInCount: 1,
    notCheckedInCount: 1, failedVerificationCount: 0,
    pendingReviewCount: 0, manualCount: 0,
  },
  {
    ...activeSession, id: "mock-cancelled-session", courseCode: "CS4301",
    courseName: "Artificial Intelligence", status: "cancelled",
    activatedAt: null, closedAt: null, requiresQr: false,
    cancelledAt: time(-5),
    cancellationReason: "The lecturer is unwell and could not attend.",
    enrolledCount: 3, presentCount: 0, lateCount: 0, absentCount: 0,
    checkedInCount: 0, lateCheckedInCount: 0, notCheckedInCount: 3,
    failedVerificationCount: 0, pendingReviewCount: 0, manualCount: 0,
  },
];

// C10 returns a summary only when finalization is bound; both outcomes are valid.
export const mockFinalizationSummary: ApiFinalizationSummary = {
  enrolledCount: 5, presentCount: 2, lateCount: 1, absentCount: 2,
  keptManualCount: 1, reconciledCount: 1, deactivatedQrBatchCount: 2,
  finalizedAt: time(0),
};
export const mockCloseSessionWithSummary = {
  ...activeSession, status: "closed" as const, closedAt: time(0),
  finalization: mockFinalizationSummary,
};
export const mockCloseSessionWithoutSummary = {
  ...activeSession, status: "closed" as const, closedAt: time(0),
  finalization: null,
};
export const mockCancelSessionResponse: ApiLecturerSession = {
  ...activeSession, status: "cancelled", closedAt: null,
};

const baseStudent: ApiSessionStudent = {
  studentId: "student-1", registrationNumber: "2307001", fullName: "Nimali Perera",
  verificationStatus: "checked_in", geofenceStatus: "passed", faceStatus: "passed",
  faceSimilarityScore: 0.94, faceLivenessPassed: true, qrStatus: null,
  attendanceStatus: null, reviewStatus: null, checkedInAt: time(-8),
  failureReason: null, initialCheckInStatus: "checked_in", qrRequiredCount: 2,
  qrPassedCount: 1, recordSource: null, manualReason: null, recordUpdatedAt: null,
};

export const mockLecturerStudents: Record<string, ApiSessionStudent[]> = {
  "mock-live-session": [
    baseStudent,
    {
      ...baseStudent, studentId: "student-2", registrationNumber: "2307002",
      fullName: "Kavin Silva", checkedInAt: time(-2),
      initialCheckInStatus: "late_checked_in", qrRequiredCount: 1, qrPassedCount: 0,
      attendanceStatus: "present", recordSource: "manual",
      manualReason: "Lecturer confirmed attendance", recordUpdatedAt: time(-1),
    },
    {
      ...baseStudent, studentId: "student-3", registrationNumber: "2307003",
      fullName: "Farah Ahmed", verificationStatus: "in_progress",
      faceStatus: null, faceSimilarityScore: null, faceLivenessPassed: null,
      checkedInAt: null, initialCheckInStatus: null,
      qrRequiredCount: null, qrPassedCount: null,
    },
    {
      ...baseStudent, studentId: "student-4", registrationNumber: "2307004",
      fullName: "Dilshan Fernando", verificationStatus: "failed",
      geofenceStatus: "failed", faceStatus: null,
      faceSimilarityScore: null, faceLivenessPassed: null,
      checkedInAt: null, initialCheckInStatus: null, failureReason: "OUTSIDE_GEOFENCE",
      qrRequiredCount: null, qrPassedCount: null, reviewStatus: "pending",
    },
    {
      ...baseStudent, studentId: "student-5", registrationNumber: "2307005",
      fullName: "Ayesha Jayasuriya", verificationStatus: null,
      geofenceStatus: null, faceStatus: null, faceSimilarityScore: null,
      faceLivenessPassed: null, checkedInAt: null, initialCheckInStatus: null,
      qrRequiredCount: null, qrPassedCount: null,
    },
  ],
  "mock-closed-session": [
    { ...baseStudent, studentId: "student-6", registrationNumber: "2307006",
      fullName: "Ravi Kumar", qrRequiredCount: null, qrPassedCount: null,
      attendanceStatus: "present", recordSource: "automatic", recordUpdatedAt: time(-90) },
  ],
};

export const mockLecturerQrBatches: Record<string, LecturerQrBatch[]> = {
  "mock-live-session": [
    {
      qrSessionId: "mock-qr-2", mode: "dynamic", status: "active",
      activatedAt: time(-4), deactivatedAt: null, expiresAt: time(20),
      voided: false, voidReason: null, requiredStudentCount: 2, passedStudentCount: 1,
    },
    {
      qrSessionId: "mock-qr-1", mode: "static", status: "deactivated",
      activatedAt: time(-9), deactivatedAt: time(-4), expiresAt: time(20),
      voided: false, voidReason: null, requiredStudentCount: 1, passedStudentCount: 1,
    },
  ],
};

export const mockLecturerTimetable: ApiLecturerTimetableEntry[] = [{
  id: "mock-timetable", courseCode: "CS3203",
  courseName: "Software Engineering Project", dayOfWeek: (new Date().getDay() + 6) % 7,
  startTime: time(-10), endTime: time(80), classroomCode: "LT-301", buildingName: "Main",
}];

export const mockLecturerDashboardOverview: ApiLecturerDashboardOverview = {
  activeCourseCount: 3, upcomingSessionCount: 0, todaySessionCount: 3,
  averageAttendanceRatePercent: 75, pendingReviewCount: 1,
};

export const mockLecturerAttendanceTrend: ApiWeeklyTrendPoint[] = [
  { label: "Week 1", attendanceRate: 72 },
  { label: "Week 2", attendanceRate: 75 },
];
