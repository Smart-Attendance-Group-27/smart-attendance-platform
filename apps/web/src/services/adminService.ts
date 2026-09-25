import "server-only";
import {
  getAcademicData as fetchAcademicData,
  getAcademicOptions as fetchAcademicOptions,
  getAccountProvisioningOptions,
  getAdminDashboardOverview,
  getAttendancePolicy as fetchAttendancePolicy,
  getAuditLogs as fetchAuditLogs,
  getBuildings as fetchBuildings,
  getAdminCorrectionRequests,
  getClassrooms,
  getInstitutionReports as fetchInstitutionReports,
  getReferenceFaces as fetchReferenceFaces,
  getUserDirectory as fetchUserDirectory,
} from "@/lib/api/admin";
import { toCorrectionRequestRow } from "@/lib/api/correctionRequestRows";
import type { CorrectionRequestRow } from "@/lib/correctionRequests";
import { formatDateLabel, formatDateTimeLabel, formatDayOfWeek, formatTimeRange, roundToOneDecimal } from "@/lib/api/format";
import {
  AcademicData,
  AcademicOption,
  AcademicReferenceData,
  AccountStatus,
  AdminDashboardData,
  AttendancePolicy,
  AuditLogEntry,
  BuildingOption,
  Classroom,
  InstitutionReportsData,
  ReadinessStatus,
  ReferenceFaceRecord,
  UserDirectoryData,
} from "@/types/admin";

// Administrator views read current data from the core-backend API.

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

function mapAccountStatus(status: string): AccountStatus {
  if (status === "active" || status === "inactive" || status === "suspended" || status === "locked") {
    return status;
  }
  return "unknown";
}

export async function getBuildingOptions(): Promise<BuildingOption[]> {
  const buildings = await fetchBuildings();
  return buildings.map((building) => ({ id: building.id, buildingName: building.buildingName }));
}

export async function getAdminDashboard(): Promise<AdminDashboardData> {
  const [overview, classrooms, policy] = await Promise.all([
    getAdminDashboardOverview(), getClassrooms(), fetchAttendancePolicy(),
  ]);

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
    policy,
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

export async function getAttendancePolicy(): Promise<AttendancePolicy> {
  return fetchAttendancePolicy();
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
      accountStatus: mapAccountStatus(student.accountStatus),
      profileStatus: student.profileStatus as UserDirectoryData["students"][number]["profileStatus"],
    })),
    lecturers: directory.lecturers.map((lecturer) => ({
      userId: lecturer.userId,
      employeeNumber: lecturer.employeeNumber,
      fullName: lecturer.fullName,
      email: lecturer.email,
      department: lecturer.department ?? "",
      designation: lecturer.designation ?? "",
      accountStatus: mapAccountStatus(lecturer.accountStatus),
      profileStatus: lecturer.profileStatus as UserDirectoryData["lecturers"][number]["profileStatus"],
    })),
    administrators: directory.administrators.map((administrator) => ({
      userId: administrator.userId,
      fullName: administrator.fullName,
      email: administrator.email,
      department: administrator.department ?? "",
      administrativeScope: administrator.administrativeScope ?? "",
      accountStatus: mapAccountStatus(administrator.accountStatus),
      profileStatus: administrator.profileStatus as UserDirectoryData["administrators"][number]["profileStatus"],
    })),
  };
}

export async function getProvisioningDepartments(): Promise<AcademicOption[]> {
  const options = await getAccountProvisioningOptions();
  return options.departments;
}

export async function getAcademicData(): Promise<AcademicData> {
  const data = await fetchAcademicData();

  return {
    sourceConnectionStatus: data.sourceConnectionStatus as AcademicData["sourceConnectionStatus"],
    courses: data.courses.map((course) => ({
      courseId: course.courseId,
      courseCode: course.courseCode,
      courseName: course.courseName,
      departmentId: course.departmentId ?? "",
      department: course.department ?? "",
      credits: course.credits ?? 0,
      status: course.status === "active" ? "active" : "inactive",
    })),
    offerings: data.offerings.map((offering) => ({
      offeringId: offering.offeringId,
      courseId: offering.courseId,
      semesterId: offering.semesterId,
      lecturerId: offering.lecturerId ?? "",
      lecturerName: offering.lecturerName ?? "",
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
      courseOfferingId: entry.courseOfferingId,
      classroomId: entry.classroomId ?? "",
      courseCode: entry.courseCode,
      courseName: entry.courseName,
      day: formatDayOfWeek(entry.dayOfWeek),
      timeRange: formatTimeRange(entry.startTime, entry.endTime),
      room: entry.classroomCode ?? "—",
      lecturerName: entry.lecturerName ?? "—",
      dayOfWeek: entry.dayOfWeek,
      startTime: entry.startTime,
      endTime: entry.endTime,
      courseType: entry.courseType ?? "",
      validFrom: entry.validFrom,
      validUntil: entry.validUntil ?? "",
      status: entry.status === "active" ? "active" : "inactive",
    })),
    enrolments: data.enrolments.map((enrolment) => ({
      enrolmentId: enrolment.enrolmentId,
      courseOfferingId: enrolment.courseOfferingId,
      studentId: enrolment.studentId,
      studentName: enrolment.studentName,
      registrationNumber: enrolment.registrationNumber,
      courseCode: enrolment.courseCode,
      semesterLabel: enrolment.semesterLabel,
      enrolmentStatus: enrolment.enrolmentStatus === "enrolled" ? "enrolled" : "dropped",
    })),
  };
}

export async function getAcademicReferenceData(): Promise<AcademicReferenceData> {
  return fetchAcademicOptions();
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
  const reports = await fetchInstitutionReports();

  return {
    summary: {
      overallAttendancePercent: roundToOneDecimal(reports.summary.overallAttendancePercent),
      totalSessionsCompleted: reports.summary.totalSessionsCompleted,
      totalStudents: reports.summary.totalStudents,
      totalLecturers: reports.summary.totalLecturers,
      studentsAtRiskCount: reports.summary.studentsAtRiskCount,
    },
    attendanceTrend: reports.attendanceTrend.map((point) => ({
      label: point.label,
      attendanceRate: point.attendanceRate,
    })),
    attendanceByFaculty: reports.attendanceByFaculty.map((item) => ({
      facultyName: item.facultyName,
      attendanceRatePercent: roundToOneDecimal(item.attendanceRatePercent),
    })),
    atRiskCourses: reports.atRiskCourses.map((item) => ({
      courseCode: item.courseCode,
      courseName: item.courseName,
      attendanceRatePercent: roundToOneDecimal(item.attendanceRatePercent),
    })),
  };
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

export async function getCorrectionRequests(): Promise<CorrectionRequestRow[]> {
  return (await getAdminCorrectionRequests()).map(toCorrectionRequestRow);
}
