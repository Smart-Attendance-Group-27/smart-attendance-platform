import "server-only";
import { getCurrentUser } from "@/lib/auth/dal";
import {
  ApiLecturerSession,
  ApiManualReviewQueueItem,
  ApiSessionStatus,
  getLecturerAtRiskStudents,
  getLecturerAttendanceTrend,
  getLecturerCourses as fetchLecturerCourses,
  getLecturerDashboardOverview,
  getLecturerSessionDetail,
  getLecturerSessionStudents,
  getLecturerQrBatches,
  getLecturerSessions,
  getLecturerTimetable,
  getManualReviewQueue,
} from "@/lib/api/lecturer";
import { formatClockTime, formatDateLabel, formatDayOfWeek, formatTimeRange, roundToOneDecimal } from "@/lib/api/format";
import { isWebMockMode } from "@/lib/api/mode";
import {
  AtRiskStudent,
  LecturerCoursesData,
  LecturerOverview,
  LecturerReportsData,
  ReviewCase,
  ReviewIssueType,
  LiveSessionDetail,
  LecturerQrBatch,
  SessionStatus,
  TimetableOption,
  TodayLecture,
} from "@/types/lecturer";

// Stage 6: every export below now calls the real core-backend API (see
// lib/api/lecturer.ts) through the caller's own Keycloak session.
// Stage 9 added real weekly attendance trends and at-risk-student detection
// (both computed server-side from attendance_records — see
// modules/academic/lecturer_reports). One field still has no backing
// feature: a live "recent activity" / "attention items" event feed. That
// stays an empty array rather than fabricated content.

function mapSessionStatus(status: ApiSessionStatus): SessionStatus {
  return status === "active" ? "in_progress" : status;
}

function isToday(iso: string): boolean {
  const date = new Date(iso);
  const now = new Date();
  return (
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  );
}

function isCheckInOpen(session: ApiLecturerSession, now: Date): boolean {
  if (session.status !== "active") return false;
  if (!session.checkInOpensAt || !session.checkInClosesAt) return false;
  const opensAt = new Date(session.checkInOpensAt).getTime();
  const closesAt = new Date(session.checkInClosesAt).getTime();
  const current = now.getTime();
  return current >= opensAt && current < closesAt;
}

// Delta between the two most recent points in a weekly trend series. Needs at
// least two real weeks of data to mean anything; returns a neutral 0 rather
// than a fabricated number when there's only one point (or none).
function computeLatestWeekDelta(trend: { attendanceRate: number }[]): number {
  if (trend.length < 2) return 0;
  const latest = trend[trend.length - 1].attendanceRate;
  const previous = trend[trend.length - 2].attendanceRate;
  return roundToOneDecimal(latest - previous);
}

function mapToTodayLecture(session: ApiLecturerSession): TodayLecture {
  return {
    sessionId: session.id,
    courseCode: session.courseCode,
    courseName: session.courseName,
    timeRange: formatTimeRange(session.scheduledStartAt, session.scheduledEndAt),
    room: session.classroomCode ?? "—",
    checkInWindow: formatTimeRange(session.checkInOpensAt, session.checkInClosesAt),
    presentCount: session.presentCount,
    checkedInCount: session.checkedInCount,
    lateCheckedInCount: session.lateCheckedInCount,
    failedVerificationCount: session.failedVerificationCount,
    notCheckedInCount: session.notCheckedInCount,
    enrolledCount: session.enrolledCount,
    status: mapSessionStatus(session.status),
  };
}

export async function getLecturerOverview(): Promise<LecturerOverview> {
  const [sessions, overview, trend] = await Promise.all([
    getLecturerSessions(),
    getLecturerDashboardOverview(),
    getLecturerAttendanceTrend(),
  ]);

  const now = new Date();
  const todaySessions = sessions.filter((session) => isToday(session.scheduledStartAt));

  return {
    summary: {
      activeLectures: sessions.filter((session) => session.status === "active").length,
      checkInWindowsOpen: sessions.filter((session) => isCheckInOpen(session, now)).length,
      studentsCheckedIn: todaySessions.reduce(
        (total, session) => total + session.checkedInCount + session.lateCheckedInCount,
        0,
      ),
      pendingReview: overview.pendingReviewCount,
      // core-backend doesn't yet distinguish "needs lecturer action" from the
      // rest of the pending-review queue, so this mirrors the total.
      pendingReviewNeedingAction: overview.pendingReviewCount,
      attendanceRatePercent: roundToOneDecimal(overview.averageAttendanceRatePercent),
      attendanceRateDeltaPercent: computeLatestWeekDelta(trend),
    },
    todayLectures: todaySessions
      .sort((a, b) => a.scheduledStartAt.localeCompare(b.scheduledStartAt))
      .map(mapToTodayLecture),
    // No event feed exists yet for "items needing attention".
    attentionItems: [],
    weeklyTrend: trend.map((point) => ({ label: point.label, attendanceRate: point.attendanceRate })),
    // No recent-activity feed exists yet.
    recentActivity: [],
  };
}

export async function getLecturerCourses(): Promise<LecturerCoursesData> {
  const [user, courses, timetable] = await Promise.all([
    getCurrentUser(),
    fetchLecturerCourses(),
    getLecturerTimetable(),
  ]);

  const lecturerName = user?.name ?? "";

  return {
    // No single "current semester" label is exposed by the courses API yet.
    semesterLabel: "",
    courses: courses.map((course) => {
      const scheduleEntry = timetable.find((entry) => entry.courseCode === course.courseCode);
      return {
        courseId: course.courseOfferingId,
        courseCode: course.courseCode,
        courseName: course.courseName,
        scheduleSummary: scheduleEntry
          ? `${formatDayOfWeek(scheduleEntry.dayOfWeek)} · ${formatClockTime(scheduleEntry.startTime)} · ${scheduleEntry.classroomCode ?? "—"}`
          : "No fixed schedule",
        lecturerName,
        enrolledCount: course.enrolledCount,
        attendanceRatePercent: roundToOneDecimal(course.attendanceRatePercent),
        status: course.status === "active" ? "active" : "correction_needed",
      };
    }),
    timetable: timetable.map((entry) => ({
      id: entry.id,
      day: formatDayOfWeek(entry.dayOfWeek),
      timeRange: formatTimeRange(entry.startTime, entry.endTime),
      courseCode: entry.courseCode,
      courseName: entry.courseName,
      room: entry.classroomCode ?? "—",
      source: "Not synchronised from an external source",
    })),
    sourceStatus: [
      {
        id: "academic-source",
        time: "—",
        title: "Academic data source",
        detail: "No external LMS/SIS source is connected; course and timetable data is managed directly.",
        status: "review",
      },
    ],
  };
}

export async function getSessionList(): Promise<TodayLecture[]> {
  const sessions = await getLecturerSessions();
  return sessions
    .sort((a, b) => b.scheduledStartAt.localeCompare(a.scheduledStartAt))
    .map(mapToTodayLecture);
}

// The set of timetable slots a lecturer can start a new session from — see
// app/actions/sessions.ts and modules/attendance_sessions/lecturer_sessions
// on the backend for why creation is scoped to existing timetable entries
// rather than being fully freeform.
export async function getSessionCreationOptions(): Promise<TimetableOption[]> {
  const timetable = await getLecturerTimetable();
  return timetable.map((entry) => ({
    id: entry.id,
    label: `${entry.courseCode} · ${formatDayOfWeek(entry.dayOfWeek)} ${formatTimeRange(entry.startTime, entry.endTime)} · ${entry.classroomCode ?? "No room"}`,
  }));
}

function mapAttemptStatus(value: string | null): LiveSessionDetail["students"][number]["attemptStatus"] {
  return value === "in_progress" || value === "checked_in" || value === "failed" ? value : null;
}

function mapFinalStatus(value: string | null): LiveSessionDetail["students"][number]["finalStatus"] {
  return value === "present" || value === "late" || value === "absent" ? value : null;
}

export async function getSessionQrBatches(sessionId: string): Promise<LecturerQrBatch[]> {
  return getLecturerQrBatches(sessionId);
}

export async function getSessionDetail(sessionId: string): Promise<LiveSessionDetail | null> {
  let session: ApiLecturerSession;
  try {
    session = await getLecturerSessionDetail(sessionId);
  } catch {
    return null;
  }
  const students = await getLecturerSessionStudents(sessionId);

  return {
    sessionId: session.id,
    courseCode: session.courseCode,
    courseName: session.courseName,
    room: session.classroomCode ?? "—",
    status: mapSessionStatus(session.status),
    startedAtLabel: session.status === "cancelled" ? "Session cancelled" : session.activatedAt
      ? `Started at ${formatClockTime(session.activatedAt)}`
      : session.closedAt
        ? `Closed at ${formatClockTime(session.closedAt)}`
        : "Not started yet",
    checkInWindow: formatTimeRange(session.checkInOpensAt, session.checkInClosesAt),
    lateThreshold: formatClockTime(session.lateAfterAt),
    lecturerName: isWebMockMode() ? "Demo lecturer" : (await getCurrentUser())?.name ?? "",
    requiresFaceVerification: session.requiresFaceVerification,
    requiresQr: session.requiresQr,
    summary: {
      enrolledCount: session.enrolledCount,
      checkedInCount: session.checkedInCount,
      lateCheckedInCount: session.lateCheckedInCount,
      notCheckedInCount: session.notCheckedInCount,
      failedVerificationCount: session.failedVerificationCount,
      presentCount: session.presentCount,
      lateCount: session.lateCount,
      absentCount: session.absentCount,
      pendingReviewCount: session.pendingReviewCount,
      manualCount: session.manualCount,
    },
    students: students.map((student) => ({
      studentId: student.studentId,
      studentIndex: student.registrationNumber,
      fullName: student.fullName,
      attemptStatus: mapAttemptStatus(student.verificationStatus),
      initialCheckInStatus: student.initialCheckInStatus,
      faceStatus: student.faceStatus,
      failureReason: student.failureReason,
      checkedInAt: student.checkedInAt,
      qrRequiredCount: student.qrRequiredCount,
      qrPassedCount: student.qrPassedCount,
      finalStatus: mapFinalStatus(student.attendanceStatus),
      recordSource: student.recordSource,
      manualReason: student.manualReason,
      recordUpdatedAt: student.recordUpdatedAt,
      reviewStatus: student.reviewStatus,
    })),
  };
}

function deriveReviewIssue(item: ApiManualReviewQueueItem): { issueType: ReviewIssueType; issueLabel: string } {
  if (item.geofenceFailureReason === "NEAR_GEOFENCE_BOUNDARY") {
    return { issueType: "borderline_geofence", issueLabel: "Borderline geofence result" };
  }
  if (item.faceStatus === "failed") {
    return { issueType: "low_confidence_face_match", issueLabel: "Low-confidence face match" };
  }
  if (item.qrStatus === "failed") {
    return { issueType: "expired_qr_submission", issueLabel: "QR verification issue" };
  }
  return {
    issueType: "duplicate_submission",
    issueLabel: item.failureReason ? humanizeReason(item.failureReason) : "Verification issue",
  };
}

function deriveGeofenceResult(item: ApiManualReviewQueueItem): ReviewCase["geofenceResult"] {
  if (item.geofenceFailureReason === "NEAR_GEOFENCE_BOUNDARY") return "boundary";
  if (item.geofenceStatus === "failed") return "outside_radius";
  // Geofence gates face verification — if a face attempt exists at all, the
  // geofence step necessarily passed first.
  return "within_radius";
}

function humanizeReason(reason: string): string {
  return reason
    .toLowerCase()
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function buildReviewReason(item: ApiManualReviewQueueItem, faceScorePercent: number): string {
  if (item.geofenceFailureReason === "NEAR_GEOFENCE_BOUNDARY") {
    return "The student's location reading was near the edge of the configured geofence radius.";
  }
  if (item.faceStatus === "failed") {
    return `The submitted face similarity score (${faceScorePercent}%) did not pass the configured threshold.`;
  }
  if (item.qrStatus === "failed") {
    return "The QR verification step did not pass.";
  }
  if (item.failureReason) {
    return `Verification failed: ${humanizeReason(item.failureReason)}.`;
  }
  return "This verification attempt requires manual review.";
}

export async function getReviewCases(): Promise<ReviewCase[]> {
  const items = await getManualReviewQueue();

  return items.map((item) => {
    const faceScorePercent = Math.round((item.faceSimilarityScore ?? 0) * 100);
    const { issueType, issueLabel } = deriveReviewIssue(item);

    return {
      caseId: item.verificationAttemptId,
      studentId: item.studentId,
      studentIndex: item.registrationNumber,
      studentName: item.fullName,
      // No programme/major is tracked on academic.student_profiles.
      studentProgramme: "",
      courseCode: item.courseCode,
      issueType,
      issueLabel,
      faceScorePercent,
      geofenceResult: deriveGeofenceResult(item),
      time: formatClockTime(item.startedAt),
      status: "pending",
      livenessPassed: item.faceLivenessPassed ?? false,
      // No distance-from-centre value is exposed on the review queue yet —
      // only the pass/fail/boundary outcome is.
      geofenceDistanceMeters: 0,
      qrEventLabel: item.qrStatus === null ? "Not required" : item.qrStatus === "passed" ? "Submitted and verified" : "Submitted but not verified",
      reviewReason: buildReviewReason(item, faceScorePercent),
    };
  });
}

function mapRiskLevel(attendanceRatePercent: number): AtRiskStudent["riskLevel"] {
  return attendanceRatePercent < 50 ? "high" : "medium";
}

export async function getLecturerReports(): Promise<LecturerReportsData> {
  const [sessions, overview, courses, trend, atRiskStudents] = await Promise.all([
    getLecturerSessions(),
    getLecturerDashboardOverview(),
    fetchLecturerCourses(),
    getLecturerAttendanceTrend(),
    getLecturerAtRiskStudents(),
  ]);

  const closedSessions = sessions.filter((session) => session.status === "closed");
  const totalPresentPlusLate = closedSessions.reduce((sum, s) => sum + s.presentCount + s.lateCount, 0);
  const totalLate = closedSessions.reduce((sum, s) => sum + s.lateCount, 0);
  const averageLateRatePercent = totalPresentPlusLate > 0 ? roundToOneDecimal((totalLate / totalPresentPlusLate) * 100) : 0;

  return {
    summary: {
      overallAttendancePercent: roundToOneDecimal(overview.averageAttendanceRatePercent),
      sessionsCompleted: closedSessions.length,
      averageLateRatePercent,
      // No historical late-rate-specific series exists to compare against —
      // only the overall attendance trend does (see attendanceRateDeltaPercent
      // on the dashboard for that comparison).
      averageLateRateDeltaPercent: 0,
      studentsAtRiskCount: atRiskStudents.length,
    },
    attendanceTrend: trend.map((point) => ({ label: point.label, attendanceRate: point.attendanceRate })),
    attendanceByCourse: courses.map((course) => ({
      courseCode: course.courseCode,
      attendanceRatePercent: roundToOneDecimal(course.attendanceRatePercent),
    })),
    atRiskStudents: atRiskStudents.map((student) => ({
      studentId: student.studentId,
      studentIndex: student.registrationNumber,
      studentName: student.fullName,
      courseCode: student.courseCode,
      attendanceRatePercent: roundToOneDecimal(student.attendanceRatePercent),
      lateCount: student.lateCount,
      lastAttendedLabel: formatDateLabel(student.lastAttendedAt),
      riskLevel: mapRiskLevel(student.attendanceRatePercent),
    })),
  };
}
