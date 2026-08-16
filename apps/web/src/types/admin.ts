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
  room: string;
  building: string;
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
