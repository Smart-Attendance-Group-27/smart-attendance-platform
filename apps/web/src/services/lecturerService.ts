import "server-only";
import { getCurrentUser } from "@/lib/auth/dal";
import {
  ApiLecturerSession,
  ApiManualReviewQueueItem,
  ApiSessionStatus,
  getLecturerCourses as fetchLecturerCourses,
  getLecturerDashboardOverview,
  getLecturerSessionDetail,
  getLecturerSessionStudents,
  getLecturerSessions,
  getLecturerTimetable,
  getManualReviewQueue,
} from "@/lib/api/lecturer";
import { formatClockTime, formatDayOfWeek, formatTimeRange, roundToOneDecimal } from "@/lib/api/format";
import {
  AtRiskStudent,
  LecturerCoursesData,
  LecturerOverview,
  LecturerReportsData,
  ReviewCase,
  ReviewIssueType,
  SessionDetail,
  SessionStatus,
  SessionStudentRow,
  TodayLecture,
  VerificationOutcome,
} from "@/types/lecturer";

// Stage 6: every export below now calls the real core-backend API (see
// lib/api/lecturer.ts) through the caller's own Keycloak session. Several
// fields the original mock UI expected — weekly/trend history, at-risk
// detection, a live activity feed — have no backing feature in core-backend
// yet. Those are returned as empty/neutral rather than fabricated; see the
// Stage 6 report for the full list.

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
  if (!session.checkInOpensAt || !session.checkInClosesAt) return false;
  const opensAt = new Date(session.checkInOpensAt).getTime();
  const closesAt = new Date(session.checkInClosesAt).getTime();
  const current = now.getTime();
  return current >= opensAt && current < closesAt;
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
    enrolledCount: session.enrolledCount,
    status: mapSessionStatus(session.status),
  };
}

export async function getLecturerOverview(): Promise<LecturerOverview> {
  const [sessions, overview] = await Promise.all([
    getLecturerSessions(),
    getLecturerDashboardOverview(),
  ]);

  const now = new Date();
  const todaySessions = sessions.filter((session) => isToday(session.scheduledStartAt));

  return {
    summary: {
      activeLectures: sessions.filter((session) => session.status === "active").length,
      checkInWindowsOpen: sessions.filter((session) => isCheckInOpen(session, now)).length,
      studentsCheckedIn: todaySessions.reduce(
        (total, session) => total + session.presentCount + session.lateCount,
        0,
      ),
      pendingReview: overview.pendingReviewCount,
      // core-backend doesn't yet distinguish "needs lecturer action" from the
      // rest of the pending-review queue, so this mirrors the total.
      pendingReviewNeedingAction: overview.pendingReviewCount,
      attendanceRatePercent: roundToOneDecimal(overview.averageAttendanceRatePercent),
      // No historical baseline exists to compute a week-over-week delta from.
      attendanceRateDeltaPercent: 0,
    },
    todayLectures: todaySessions
      .sort((a, b) => a.scheduledStartAt.localeCompare(b.scheduledStartAt))
      .map(mapToTodayLecture),
    // No event feed exists yet for "items needing attention".
    attentionItems: [],
    // No historical daily/weekly attendance series exists yet.
    weeklyTrend: [],
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

function mapVerificationOutcome(status: string | null, requires: boolean): VerificationOutcome {
  if (!requires) return "not_required";
  if (status === null) return "not_submitted";
  if (status === "passed") return "present";
  if (status === "failed") return "failed";
  return "not_submitted";
}

function mapQrOutcome(status: string | null, requiresQr: boolean): VerificationOutcome {
  if (!requiresQr) return "not_required";
  if (status === null) return "not_participated";
  if (status === "passed") return "participated";
  return "not_participated";
}

function mapFinalStatus(attendanceStatus: string | null, reviewStatus: string | null): SessionStudentRow["finalStatus"] {
  if (attendanceStatus === "present" || attendanceStatus === "late") return attendanceStatus;
  if (reviewStatus === "pending") return "pending_review";
  return "absent";
}

export async function getSessionDetail(sessionId: string): Promise<SessionDetail | null> {
  let session: ApiLecturerSession;
  try {
    session = await getLecturerSessionDetail(sessionId);
  } catch {
    return null;
  }
  const students = await getLecturerSessionStudents(sessionId);

  const enrolledCount = session.enrolledCount || 1;
  const presentCount = session.presentCount;
  const lateCount = session.lateCount;
  const pendingReviewCount = session.pendingReviewCount;
  const notVerifiedCount = Math.max(enrolledCount - presentCount - lateCount - pendingReviewCount, 0);

  return {
    sessionId: session.id,
    courseCode: session.courseCode,
    courseName: session.courseName,
    room: session.classroomCode ?? "—",
    status: mapSessionStatus(session.status),
    startedAtLabel: session.activatedAt
      ? `Started at ${formatClockTime(session.activatedAt)}`
      : session.closedAt
        ? `Closed at ${formatClockTime(session.closedAt)}`
        : "Not started yet",
    checkInWindow: formatTimeRange(session.checkInOpensAt, session.checkInClosesAt),
    lateThreshold: formatClockTime(session.lateAfterAt),
    lecturerName: (await getCurrentUser())?.name ?? "",
    summary: {
      presentCount,
      presentPercent: roundToOneDecimal((presentCount / enrolledCount) * 100),
      lateCount,
      latePercent: roundToOneDecimal((lateCount / enrolledCount) * 100),
      pendingReviewCount,
      notVerifiedCount,
      notVerifiedPercent: roundToOneDecimal((notVerifiedCount / enrolledCount) * 100),
    },
    students: students.map((student) => ({
      studentId: student.studentId,
      studentIndex: student.registrationNumber,
      initialFaceCheck: mapVerificationOutcome(student.faceStatus, session.requiresFaceVerification),
      // core-backend has no separate "additional/dynamic face check" step
      // distinct from the primary face check yet.
      additionalCheck: "not_launched",
      qrVerification: mapQrOutcome(student.qrStatus, session.requiresQr),
      finalStatus: mapFinalStatus(student.attendanceStatus, student.reviewStatus),
      time: formatClockTime(student.checkedInAt),
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

export async function getLecturerReports(): Promise<LecturerReportsData> {
  const [sessions, overview, courses] = await Promise.all([
    getLecturerSessions(),
    getLecturerDashboardOverview(),
    fetchLecturerCourses(),
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
      // No historical baseline exists to compute a delta from.
      averageLateRateDeltaPercent: 0,
      // No at-risk detection exists yet — see attendanceByCourse for real
      // per-course rates instead.
      studentsAtRiskCount: 0,
    },
    // No historical weekly attendance series exists yet.
    attendanceTrend: [],
    attendanceByCourse: courses.map((course) => ({
      courseCode: course.courseCode,
      attendanceRatePercent: roundToOneDecimal(course.attendanceRatePercent),
    })),
    // No at-risk-student detection exists yet.
    atRiskStudents: [] as AtRiskStudent[],
  };
}
