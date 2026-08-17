import "server-only";
import {
  getAcademicData as fetchAcademicData,
  getAdminDashboardOverview,
  getAuditLogs as fetchAuditLogs,
  getBuildings as fetchBuildings,
  getClassrooms,
  getReferenceFaces as fetchReferenceFaces,
  getUserDirectory as fetchUserDirectory,
} from "@/lib/api/admin";
import { formatDateLabel, formatDateTimeLabel, formatDayOfWeek, formatTimeRange, roundToOneDecimal } from "@/lib/api/format";
import { MOCK_ADMIN_DASHBOARD, MOCK_INSTITUTION_REPORTS } from "@/mocks/admin";
import {
  AcademicData,
  AdminDashboardData,
  AuditLogEntry,
  BuildingOption,
  Classroom,
  InstitutionReportsData,
  ReadinessStatus,
  ReferenceFaceRecord,
  UserDirectoryData,
} from "@/types/admin";

// Stage 6: dashboard/classrooms/users/academic-data/reference-faces/audit-log
// now call the real core-backend API (see lib/api/admin.ts). Two pieces stay
// mocked, both for reasons documented in the Stage 5 report rather than lack
// of effort:
//   - `policy` (AttendancePolicy) has no backing database table yet — the
//     Stage 5 migration proposal for `academic.attendance_policies` is still
//     awaiting approval, so there is nothing real to fetch.
//   - Institution-wide reports/analytics (getInstitutionReports) were
//     explicitly scoped out of Stage 5 ("Real Administrator APIs") as a
//     separate, not-yet-built integration area.

function mapClassroomStatus(status: string): Classroom["status"] {
  return status === "active" ? "active" : "needs_review";
}

function mapReadinessStatus(status: string): ReadinessStatus {
  if (status === "not_checked" || status === "passed" || status === "failed" || status === "expired") {
    return status;
  }
  // The backend's "pending" (a face_validation_attempts row exists but hasn't
  // resolved yet) has no dedicated bucket in this UI's readiness states.
  return "not_checked";
}

export async function getBuildingOptions(): Promise<BuildingOption[]> {
  const buildings = await fetchBuildings();
  return buildings.map((building) => ({ id: building.id, buildingName: building.buildingName }));
}

export async function getAdminDashboard(): Promise<AdminDashboardData> {
  const [overview, classrooms] = await Promise.all([getAdminDashboardOverview(), getClassrooms()]);

  return {
    summary: {
      activeUsersCount: overview.activeUsersCount,
      configuredClassroomsCount: overview.configuredClassroomsCount,
      activeGeofencesCount: overview.activeGeofencesCount,
      academicSourceStatusLabel: overview.academicSourceStatusLabel,
      lastSyncLabel: "No external source connected",
      policyAlertsCount: overview.policyAlertsCount,
    },
    classrooms: classrooms.map((classroom) => ({
      classroomId: classroom.id,
      classroomCode: classroom.classroomCode,
      room: classroom.classroomCode,
      building: classroom.buildingName,
      buildingId: classroom.buildingId,
      floorNumber: classroom.floorNumber ?? 0,
      capacity: classroom.capacity ?? 0,
      latitude: classroom.latitude,
      longitude: classroom.longitude,
      defaultGeofenceRadiusMeters: classroom.defaultGeofenceRadiusM,
      assignedCoursesCount: classroom.assignedCoursesCount,
      status: mapClassroomStatus(classroom.status),
      rawStatus: classroom.status,
    })),
    // Not backed by a real table yet — see the module comment above.
    policy: MOCK_ADMIN_DASHBOARD.policy,
    academicSync: [
      {
        id: "academic-sync-1",
        time: "—",
        title: "Academic data source",
        detail: "No external academic source configured; data is managed directly.",
        status: "review",
      },
    ],
  };
}

export async function getUserDirectory(): Promise<UserDirectoryData> {
  const directory = await fetchUserDirectory();

  return {
    students: directory.students.map((student) => ({
      userId: student.userId,
      registrationNumber: student.registrationNumber,
      fullName: student.fullName,
      email: student.email,
      department: student.department ?? "",
      intakeYear: student.intakeYear ?? 0,
      currentSemester: student.currentSemester ?? 0,
      accountStatus: student.accountStatus as UserDirectoryData["students"][number]["accountStatus"],
      profileStatus: student.profileStatus as UserDirectoryData["students"][number]["profileStatus"],
    })),
    lecturers: directory.lecturers.map((lecturer) => ({
      userId: lecturer.userId,
      employeeNumber: lecturer.employeeNumber,
      fullName: lecturer.fullName,
      email: lecturer.email,
      department: lecturer.department ?? "",
      designation: lecturer.designation ?? "",
      accountStatus: lecturer.accountStatus as UserDirectoryData["lecturers"][number]["accountStatus"],
      profileStatus: lecturer.profileStatus as UserDirectoryData["lecturers"][number]["profileStatus"],
    })),
    administrators: directory.administrators.map((administrator) => ({
      userId: administrator.userId,
      fullName: administrator.fullName,
      email: administrator.email,
      department: administrator.department ?? "",
      administrativeScope: administrator.administrativeScope ?? "",
      accountStatus: administrator.accountStatus as UserDirectoryData["administrators"][number]["accountStatus"],
      profileStatus: administrator.profileStatus as UserDirectoryData["administrators"][number]["profileStatus"],
    })),
  };
}

export async function getAcademicData(): Promise<AcademicData> {
  const data = await fetchAcademicData();

  return {
    sourceConnectionStatus: data.sourceConnectionStatus as AcademicData["sourceConnectionStatus"],
    courses: data.courses.map((course) => ({
      courseId: course.courseId,
      courseCode: course.courseCode,
      courseName: course.courseName,
      department: course.department ?? "",
      credits: course.credits ?? 0,
      status: course.status === "active" ? "active" : "inactive",
    })),
    offerings: data.offerings.map((offering) => ({
      offeringId: offering.offeringId,
      courseCode: offering.courseCode,
      courseName: offering.courseName,
      semesterLabel: offering.semesterLabel,
      batchYear: offering.batchYear ?? 0,
      courseType: offering.courseType ?? "",
      attendanceThresholdPercent: roundToOneDecimal(offering.attendanceThresholdPercent),
      enrolledCount: offering.enrolledCount,
      status: offering.status === "active" ? "active" : "inactive",
    })),
    timetable: data.timetable.map((entry) => ({
      id: entry.id,
      courseCode: entry.courseCode,
      courseName: entry.courseName,
      day: formatDayOfWeek(entry.dayOfWeek),
      timeRange: formatTimeRange(entry.startTime, entry.endTime),
      room: entry.classroomCode ?? "—",
      lecturerName: entry.lecturerName ?? "—",
    })),
    enrolments: data.enrolments.map((enrolment) => ({
      enrolmentId: enrolment.enrolmentId,
      studentName: enrolment.studentName,
      registrationNumber: enrolment.registrationNumber,
      courseCode: enrolment.courseCode,
      semesterLabel: enrolment.semesterLabel,
      enrolmentStatus: enrolment.enrolmentStatus === "enrolled" ? "enrolled" : "dropped",
    })),
  };
}

export async function getReferenceFaces(): Promise<ReferenceFaceRecord[]> {
  const faces = await fetchReferenceFaces();

  return faces.map((face) => ({
    studentId: face.studentId,
    studentName: face.studentName,
    registrationNumber: face.registrationNumber,
    embeddingGenerationStatus: face.embeddingGenerationStatus as ReferenceFaceRecord["embeddingGenerationStatus"],
    readinessStatus: mapReadinessStatus(face.readinessStatus),
    generatedAtLabel: face.generatedAt ? formatDateLabel(face.generatedAt) : null,
    readinessCheckedAtLabel: face.readinessCheckedAt ? formatDateLabel(face.readinessCheckedAt) : null,
  }));
}

export async function getInstitutionReports(): Promise<InstitutionReportsData> {
  // Not backed by a real endpoint yet — see the module comment above.
  return MOCK_INSTITUTION_REPORTS;
}

export async function getAuditLog(): Promise<AuditLogEntry[]> {
  const entries = await fetchAuditLogs();

  return entries.map((entry) => ({
    id: entry.id,
    occurredAtLabel: formatDateTimeLabel(entry.occurredAt),
    actorName: entry.actorName,
    actorRole: entry.actorType === "lecturer" || entry.actorType === "administrator" ? entry.actorType : "system",
    action: entry.action,
    entityType: entry.entityType,
    entityLabel: entry.entityId ? `${entry.entityType} · ${entry.entityId.slice(0, 8)}` : entry.entityType,
    outcome: entry.outcome === "failure" ? "failure" : "success",
  }));
}
