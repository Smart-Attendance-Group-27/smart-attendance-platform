import "server-only";
import { coreBackendFetch } from "@/lib/api/coreBackend";
import { isWebMockMode } from "@/lib/api/mode";
import { MOCK_ATTENDANCE_POLICY } from "@/mocks/admin";
import type { AttendancePolicy } from "@/types/admin";

export type ApiAttendancePolicy = AttendancePolicy;
export type ApiAttendancePolicyWrite = Omit<AttendancePolicy, "updatedAt" | "updatedByName">;

export function getAttendancePolicy(): Promise<ApiAttendancePolicy> {
  if (isWebMockMode()) return Promise.resolve(MOCK_ATTENDANCE_POLICY);
  return coreBackendFetch("/api/v1/administrators/me/attendance-policy");
}

export function putAttendancePolicy(body: ApiAttendancePolicyWrite): Promise<ApiAttendancePolicy> {
  return coreBackendFetch("/api/v1/administrators/me/attendance-policy", { method: "PUT", body });
}

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

export type ApiProvisionedAccountRole = "student" | "lecturer" | "administrator";

export type ApiAccountProvisionRequest = {
  role: ApiProvisionedAccountRole;
  email: string;
  firstName: string;
  middleName?: string;
  lastName: string;
  departmentId: string;
  registrationNumber?: string;
  intakeYear?: number;
  currentSemester?: number;
  employeeNumber?: string;
  designation?: string;
  administrativeScope?: string;
};

export type ApiProvisionedAccount = {
  userId: string;
  keycloakUserId: string;
  role: ApiProvisionedAccountRole;
  email: string;
  temporaryPassword: string;
};

export type ApiAccountProvisioningOptions = {
  departments: { id: string; label: string }[];
};

export type ApiAdminCourse = {
  courseId: string;
  courseCode: string;
  courseName: string;
  departmentId: string | null;
  department: string | null;
  credits: number | null;
  status: string;
};

export type ApiAdminCourseOffering = {
  offeringId: string;
  courseId: string;
  semesterId: string;
  lecturerId: string | null;
  lecturerName: string | null;
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
  courseOfferingId: string;
  classroomId: string | null;
  courseCode: string;
  courseName: string;
  dayOfWeek: number;
  startTime: string;
  endTime: string;
  classroomCode: string | null;
  lecturerName: string | null;
  courseType: string | null;
  validFrom: string;
  validUntil: string | null;
  status: string;
};

export type ApiAdminEnrolment = {
  enrolmentId: string;
  courseOfferingId: string;
  studentId: string;
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

export type ApiAcademicOption = { id: string; label: string };

export type ApiAcademicReferenceData = {
  departments: ApiAcademicOption[];
  semesters: ApiAcademicOption[];
  lecturers: ApiAcademicOption[];
  students: ApiAcademicOption[];
  classrooms: ApiAcademicOption[];
};

export type ApiCourseWriteRequest = {
  courseCode: string;
  courseName: string;
  departmentId: string;
  credits: number;
  status: "active" | "inactive";
};

export type ApiOfferingWriteRequest = {
  courseId: string;
  semesterId: string;
  lecturerId: string;
  batchYear: number;
  courseType: string;
  attendanceThresholdPercent: number;
  status: "active" | "inactive";
};

export type ApiTimetableWriteRequest = {
  courseOfferingId: string;
  classroomId: string;
  dayOfWeek: number;
  startTime: string;
  endTime: string;
  courseType: string;
  validFrom: string;
  validUntil: string | null;
  status: "active" | "inactive";
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

export function provisionAccount(
  body: ApiAccountProvisionRequest,
): Promise<ApiProvisionedAccount> {
  return coreBackendFetch("/api/v1/administrators/me/users", { method: "POST", body });
}

export function getAccountProvisioningOptions(): Promise<ApiAccountProvisioningOptions> {
  return coreBackendFetch("/api/v1/administrators/me/users/provisioning-options");
}

export function getAcademicData(): Promise<ApiAcademicData> {
  return coreBackendFetch("/api/v1/administrators/me/academic-data");
}

export function getAcademicOptions(): Promise<ApiAcademicReferenceData> {
  return coreBackendFetch("/api/v1/administrators/me/academic-options");
}

export function createCourse(body: ApiCourseWriteRequest): Promise<ApiAdminCourse> {
  return coreBackendFetch("/api/v1/administrators/me/courses", { method: "POST", body });
}

export function updateCourse(courseId: string, body: ApiCourseWriteRequest): Promise<ApiAdminCourse> {
  return coreBackendFetch(`/api/v1/administrators/me/courses/${courseId}`, { method: "PUT", body });
}

export function createOffering(body: ApiOfferingWriteRequest): Promise<ApiAdminCourseOffering> {
  return coreBackendFetch("/api/v1/administrators/me/offerings", { method: "POST", body });
}

export function updateOffering(
  offeringId: string,
  body: ApiOfferingWriteRequest,
): Promise<ApiAdminCourseOffering> {
  return coreBackendFetch(`/api/v1/administrators/me/offerings/${offeringId}`, { method: "PUT", body });
}

export function enrolStudent(offeringId: string, studentId: string): Promise<ApiAdminEnrolment> {
  return coreBackendFetch(`/api/v1/administrators/me/offerings/${offeringId}/enrolments`, {
    method: "POST",
    body: { studentId },
  });
}

export function dropStudent(offeringId: string, studentId: string): Promise<ApiAdminEnrolment> {
  return coreBackendFetch(
    `/api/v1/administrators/me/offerings/${offeringId}/enrolments/${studentId}`,
    { method: "DELETE" },
  );
}

export function createTimetableEntry(
  body: ApiTimetableWriteRequest,
): Promise<ApiAdminTimetableEntry> {
  return coreBackendFetch("/api/v1/administrators/me/timetable-entries", { method: "POST", body });
}

export function updateTimetableEntry(
  entryId: string,
  body: ApiTimetableWriteRequest,
): Promise<ApiAdminTimetableEntry> {
  return coreBackendFetch(`/api/v1/administrators/me/timetable-entries/${entryId}`, {
    method: "PUT",
    body,
  });
}

export function deactivateTimetableEntry(entryId: string): Promise<ApiAdminTimetableEntry> {
  return coreBackendFetch(`/api/v1/administrators/me/timetable-entries/${entryId}`, {
    method: "DELETE",
  });
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
