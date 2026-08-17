import "server-only";
import { coreBackendFetch } from "@/lib/api/coreBackend";

export type ApiAdminOverview = {
  activeUsersCount: number;
  configuredClassroomsCount: number;
  activeGeofencesCount: number;
  academicSourceStatusLabel: string;
  policyAlertsCount: number;
};

export type ApiBuilding = {
  id: string;
  buildingName: string;
  status: string | null;
};

export type ApiClassroom = {
  id: string;
  buildingId: string;
  buildingName: string;
  classroomCode: string;
  floorNumber: number | null;
  capacity: number | null;
  latitude: number;
  longitude: number;
  defaultGeofenceRadiusM: number;
  status: string;
  assignedCoursesCount: number;
  createdAt: string;
  updatedAt: string;
};

export type ApiAccountStatus = "active" | "suspended" | "locked";

export type ApiStudentAccount = {
  userId: string;
  registrationNumber: string;
  fullName: string;
  email: string;
  department: string | null;
  intakeYear: number | null;
  currentSemester: number | null;
  accountStatus: string;
  profileStatus: string;
};

export type ApiLecturerAccount = {
  userId: string;
  employeeNumber: string;
  fullName: string;
  email: string;
  department: string | null;
  designation: string | null;
  accountStatus: string;
  profileStatus: string;
};

export type ApiAdministratorAccount = {
  userId: string;
  fullName: string;
  email: string;
  department: string | null;
  administrativeScope: string | null;
  accountStatus: string;
  profileStatus: string;
};

export type ApiUserDirectory = {
  students: ApiStudentAccount[];
  lecturers: ApiLecturerAccount[];
  administrators: ApiAdministratorAccount[];
};

export type ApiAdminCourse = {
  courseId: string;
  courseCode: string;
  courseName: string;
  department: string | null;
  credits: number | null;
  status: string;
};

export type ApiAdminCourseOffering = {
  offeringId: string;
  courseCode: string;
  courseName: string;
  semesterLabel: string;
  batchYear: number | null;
  courseType: string | null;
  attendanceThresholdPercent: number | null;
  enrolledCount: number;
  status: string;
};

export type ApiAdminTimetableEntry = {
  id: string;
  courseCode: string;
  courseName: string;
  dayOfWeek: number;
  startTime: string;
  endTime: string;
  classroomCode: string | null;
  lecturerName: string | null;
};

export type ApiAdminEnrolment = {
  enrolmentId: string;
  studentName: string;
  registrationNumber: string;
  courseCode: string;
  semesterLabel: string;
  enrolmentStatus: string;
};

export type ApiAcademicData = {
  sourceConnectionStatus: string;
  courses: ApiAdminCourse[];
  offerings: ApiAdminCourseOffering[];
  timetable: ApiAdminTimetableEntry[];
  enrolments: ApiAdminEnrolment[];
};

export type ApiReferenceFace = {
  studentId: string;
  studentName: string;
  registrationNumber: string;
  embeddingGenerationStatus: string;
  readinessStatus: string;
  generatedAt: string | null;
  readinessCheckedAt: string | null;
};

export type ApiAuditLogEntry = {
  id: string;
  occurredAt: string;
  actorUserId: string | null;
  actorType: string;
  actorName: string;
  action: string;
  entityType: string;
  entityId: string | null;
  outcome: string;
  failureReason: string | null;
};

export function getAdminDashboardOverview(): Promise<ApiAdminOverview> {
  return coreBackendFetch("/api/v1/administrators/me/dashboard-overview");
}

export type ApiClassroomWriteRequest = {
  buildingId: string;
  classroomCode: string;
  floorNumber: number | null;
  capacity: number | null;
  latitude: number;
  longitude: number;
  defaultGeofenceRadiusM: number;
  status: string;
};

export function getBuildings(): Promise<ApiBuilding[]> {
  return coreBackendFetch("/api/v1/administrators/me/buildings");
}

export function getClassrooms(): Promise<ApiClassroom[]> {
  return coreBackendFetch("/api/v1/administrators/me/classrooms");
}

export function createClassroom(body: ApiClassroomWriteRequest): Promise<ApiClassroom> {
  return coreBackendFetch("/api/v1/administrators/me/classrooms", { method: "POST", body });
}

export function updateClassroom(
  classroomId: string,
  body: ApiClassroomWriteRequest,
): Promise<ApiClassroom> {
  return coreBackendFetch(`/api/v1/administrators/me/classrooms/${classroomId}`, {
    method: "PUT",
    body,
  });
}

export function getUserDirectory(): Promise<ApiUserDirectory> {
  return coreBackendFetch("/api/v1/administrators/me/users");
}

export function updateAccountStatus(
  userId: string,
  accountStatus: "active" | "suspended",
): Promise<{ userId: string; accountStatus: string }> {
  return coreBackendFetch(`/api/v1/administrators/me/users/${userId}/account-status`, {
    method: "PATCH",
    body: { accountStatus },
  });
}

export function getAcademicData(): Promise<ApiAcademicData> {
  return coreBackendFetch("/api/v1/administrators/me/academic-data");
}

export function getReferenceFaces(): Promise<ApiReferenceFace[]> {
  return coreBackendFetch("/api/v1/administrators/me/reference-faces");
}

export function getAuditLogs(limit = 200): Promise<ApiAuditLogEntry[]> {
  return coreBackendFetch("/api/v1/administrators/me/audit-logs", { searchParams: { limit } });
}

export type ApiInstitutionSummary = {
  overallAttendancePercent: number;
  totalSessionsCompleted: number;
  totalStudents: number;
  totalLecturers: number;
  studentsAtRiskCount: number;
};

export type ApiWeeklyTrendPoint = {
  label: string;
  attendanceRate: number;
};

export type ApiFacultyAttendance = {
  facultyName: string;
  attendanceRatePercent: number;
};

export type ApiAtRiskCourse = {
  courseCode: string;
  courseName: string;
  attendanceRatePercent: number;
};

export type ApiInstitutionReports = {
  summary: ApiInstitutionSummary;
  attendanceTrend: ApiWeeklyTrendPoint[];
  attendanceByFaculty: ApiFacultyAttendance[];
  atRiskCourses: ApiAtRiskCourse[];
};

export function getInstitutionReports(): Promise<ApiInstitutionReports> {
  return coreBackendFetch("/api/v1/administrators/me/institution-reports");
}
