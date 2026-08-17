// Field names follow academic.classrooms / academic.faculties (database/smart_attendance_db_clean.sql)
// where a matching column already exists, so a future services/admin.ts can map API
// responses onto these types without renaming anything downstream.

export type AdminOverviewSummary = {
  activeUsersCount: number;
  configuredClassroomsCount: number;
  activeGeofencesCount: number;
  academicSourceStatusLabel: string;
  lastSyncLabel: string;
  policyAlertsCount: number;
};

export type ClassroomStatus = "active" | "needs_review";

export type Classroom = {
  classroomId: string;
  classroomCode: string;
  room: string;
  building: string;
  floorNumber: number;
  capacity: number;
  latitude: number;
  longitude: number;
  defaultGeofenceRadiusMeters: number;
  assignedCoursesCount: number;
  status: ClassroomStatus;
};

export type AttendancePolicy = {
  checkInWindowMinutes: number;
  lateThresholdMinutes: number;
  faceConfidenceThresholdPercent: number;
  additionalFaceCheckPolicyLabel: string;
  dynamicQrPolicyLabel: string;
  qrWindowMinutes: number;
};

export type SyncStatus = "current" | "review";

export type AcademicSyncItem = {
  id: string;
  time: string;
  title: string;
  detail: string;
  status: SyncStatus;
};

export type AdminDashboardData = {
  summary: AdminOverviewSummary;
  classrooms: Classroom[];
  policy: AttendancePolicy;
  academicSync: AcademicSyncItem[];
};

// --- User administration -------------------------------------------------
// Field names follow identity.users (account_status) plus the relevant
// academic.*_profiles table for each account kind. Credentials stay in
// Keycloak — nothing here models a password.

export type AccountStatus = "active" | "suspended" | "locked";
export type ProfileStatus = "active" | "inactive";

export type StudentAccount = {
  userId: string;
  registrationNumber: string;
  fullName: string;
  email: string;
  department: string;
  intakeYear: number;
  currentSemester: number;
  accountStatus: AccountStatus;
  profileStatus: ProfileStatus;
};

export type LecturerAccount = {
  userId: string;
  employeeNumber: string;
  fullName: string;
  email: string;
  department: string;
  designation: string;
  accountStatus: AccountStatus;
  profileStatus: ProfileStatus;
};

export type AdministratorAccount = {
  userId: string;
  fullName: string;
  email: string;
  department: string;
  administrativeScope: string;
  accountStatus: AccountStatus;
  profileStatus: ProfileStatus;
};

export type UserDirectoryData = {
  students: StudentAccount[];
  lecturers: LecturerAccount[];
  administrators: AdministratorAccount[];
};

// --- Academic data (administrator view) -----------------------------------
// Administrators manage/synchronise this data; lecturers only ever see the
// read-only subset assigned to them (apps/web/src/types/lecturer.ts).

export type AcademicRecordStatus = "active" | "inactive";

export type AdminCourse = {
  courseId: string;
  courseCode: string;
  courseName: string;
  department: string;
  credits: number;
  status: AcademicRecordStatus;
};

export type CourseOffering = {
  offeringId: string;
  courseCode: string;
  courseName: string;
  semesterLabel: string;
  batchYear: number;
  courseType: string;
  attendanceThresholdPercent: number;
  enrolledCount: number;
  status: AcademicRecordStatus;
};

export type AdminTimetableEntry = {
  id: string;
  courseCode: string;
  courseName: string;
  day: string;
  timeRange: string;
  room: string;
  lecturerName: string;
};

export type Enrolment = {
  enrolmentId: string;
  studentName: string;
  registrationNumber: string;
  courseCode: string;
  semesterLabel: string;
  enrolmentStatus: "enrolled" | "dropped";
};

export type AcademicSourceConnectionStatus = "not_configured" | "connected";

export type AcademicData = {
  sourceConnectionStatus: AcademicSourceConnectionStatus;
  courses: AdminCourse[];
  offerings: CourseOffering[];
  timetable: AdminTimetableEntry[];
  enrolments: Enrolment[];
};

// --- Reference-face governance ---------------------------------------------
// Mirrors face_verification.face_profiles metadata only — never the
// embedding vector itself, which this type intentionally has no field for.

export type EmbeddingGenerationStatus = "pending" | "generated" | "failed" | "revoked";
export type ReadinessStatus = "not_checked" | "passed" | "failed" | "expired";

export type ReferenceFaceRecord = {
  studentId: string;
  studentName: string;
  registrationNumber: string;
  embeddingGenerationStatus: EmbeddingGenerationStatus;
  readinessStatus: ReadinessStatus;
  generatedAtLabel: string | null;
  readinessCheckedAtLabel: string | null;
};

// --- Institution-level reports ----------------------------------------------

export type AtRiskCourse = {
  courseCode: string;
  courseName: string;
  attendanceRatePercent: number;
};

export type InstitutionReportsData = {
  summary: {
    overallAttendancePercent: number;
    totalSessionsCompleted: number;
    totalStudents: number;
    totalLecturers: number;
    studentsAtRiskCount: number;
  };
  attendanceTrend: { label: string; attendanceRate: number }[];
  attendanceByFaculty: { facultyName: string; attendanceRatePercent: number }[];
  atRiskCourses: AtRiskCourse[];
};

// --- Audit log --------------------------------------------------------------
// Mirrors audit.audit_logs — schema-only today (see services/adminService.ts),
// mock data here previews the UI ahead of write-side instrumentation.

export type AuditOutcome = "success" | "failure";

export type AuditLogEntry = {
  id: string;
  occurredAtLabel: string;
  actorName: string;
  actorRole: "lecturer" | "administrator" | "system";
  action: string;
  entityType: string;
  entityLabel: string;
  outcome: AuditOutcome;
};
