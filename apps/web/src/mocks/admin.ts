// MOCK DATA — no administrator-facing backend endpoints exist yet (see repo inspection
// notes). services/adminService.ts wraps every export below behind the same shapes
// (apps/web/src/types/admin.ts) so real API responses drop in without page rewrites.
//
// No university LMS/SIS connector exists or is credentialed anywhere in this repo —
// "academicSourceStatusLabel"/"sourceConnectionStatus" below are deliberately set to
// reflect that (not "Connected"), per the project rule against inventing an external
// integration that isn't real.
import {
  AcademicData,
  AdministratorAccount,
  AdminDashboardData,
  AuditLogEntry,
  InstitutionReportsData,
  LecturerAccount,
  ReferenceFaceRecord,
  StudentAccount,
  UserDirectoryData,
} from "@/types/admin";

export const MOCK_ADMIN_DASHBOARD: AdminDashboardData = {
  summary: {
    activeUsersCount: 4286,
    configuredClassroomsCount: 28,
    activeGeofencesCount: 24,
    academicSourceStatusLabel: "Not configured",
    lastSyncLabel: "No external source connected",
    policyAlertsCount: 2,
  },
  classrooms: [
    { classroomId: "room-cs-lab-01", classroomCode: "CS-LAB-01", room: "CS-Lab-01", building: "CSE Building", buildingId: "building-cse", floorNumber: 1, capacity: 60, latitude: 6.7961, longitude: 79.9007, defaultGeofenceRadiusMeters: 25, assignedCoursesCount: 3, status: "active", rawStatus: "active" },
    { classroomId: "room-lt-301", classroomCode: "LT-301", room: "LT-301", building: "Sumanadasa Building", buildingId: "building-sumanadasa", floorNumber: 3, capacity: 120, latitude: 6.7963, longitude: 79.9009, defaultGeofenceRadiusMeters: 30, assignedCoursesCount: 4, status: "active", rawStatus: "active" },
    { classroomId: "room-lt-204", classroomCode: "LT-204", room: "LT-204", building: "CSE Building", buildingId: "building-cse", floorNumber: 2, capacity: 90, latitude: 6.7960, longitude: 79.9005, defaultGeofenceRadiusMeters: 30, assignedCoursesCount: 2, status: "active", rawStatus: "active" },
    { classroomId: "room-ai-lab-02", classroomCode: "AI-LAB-02", room: "AI-Lab-02", building: "Innovation Hub", buildingId: "building-innovation-hub", floorNumber: 1, capacity: 40, latitude: 6.7965, longitude: 79.9012, defaultGeofenceRadiusMeters: 20, assignedCoursesCount: 2, status: "needs_review", rawStatus: "inactive" },
  ],
  policy: {
    checkInWindowMinutes: 10,
    lateThresholdMinutes: 5,
    faceConfidenceThresholdPercent: 75,
    additionalFaceCheckPolicyLabel: "Lecturer may launch when needed",
    dynamicQrPolicyLabel: "Optional and lecturer-controlled",
    qrWindowMinutes: 15,
  },
  academicSync: [
    { id: "sync-1", time: "—", title: "Course catalogue", detail: "No external academic source configured", status: "review" },
    { id: "sync-2", time: "—", title: "Student enrolments", detail: "Managed locally until a source is connected", status: "review" },
  ],
};

const STUDENTS: StudentAccount[] = [
  { userId: "user-stu-1", registrationNumber: "230714A", fullName: "Oshadha Wijayarathne", email: "230714a@uom.lk", department: "Computer Science and Engineering", intakeYear: 2023, currentSemester: 5, accountStatus: "active", profileStatus: "active" },
  { userId: "user-stu-2", registrationNumber: "230738B", fullName: "Benjamin Ong", email: "230738b@uom.lk", department: "Computer Science and Engineering", intakeYear: 2023, currentSemester: 5, accountStatus: "active", profileStatus: "active" },
  { userId: "user-stu-3", registrationNumber: "230741C", fullName: "Chloe Lim", email: "230741c@uom.lk", department: "Computer Science and Engineering", intakeYear: 2023, currentSemester: 5, accountStatus: "active", profileStatus: "active" },
  { userId: "user-stu-4", registrationNumber: "230799F", fullName: "Fiona Chang", email: "230799f@uom.lk", department: "Computer Science and Engineering", intakeYear: 2023, currentSemester: 5, accountStatus: "suspended", profileStatus: "active" },
  { userId: "user-stu-5", registrationNumber: "230876A", fullName: "Aisha Rahman", email: "230876a@uom.lk", department: "Computer Science and Engineering", intakeYear: 2023, currentSemester: 5, accountStatus: "active", profileStatus: "active" },
  { userId: "user-stu-6", registrationNumber: "230589B", fullName: "Brandon Lee", email: "230589b@uom.lk", department: "Computer Science and Engineering", intakeYear: 2023, currentSemester: 5, accountStatus: "active", profileStatus: "active" },
];

const LECTURERS: LecturerAccount[] = [
  { userId: "user-lec-1", employeeNumber: "EMP-1042", fullName: "Prof. Dulani Meedeniya", email: "dulani@uom.lk", department: "Computer Science and Engineering", designation: "Professor", accountStatus: "active", profileStatus: "active" },
  { userId: "user-lec-2", employeeNumber: "EMP-1077", fullName: "Dr. Kasun Perera", email: "kasun.perera@uom.lk", department: "Computer Science and Engineering", designation: "Senior Lecturer", accountStatus: "active", profileStatus: "active" },
  { userId: "user-lec-3", employeeNumber: "EMP-1103", fullName: "Dr. Nadeesha Silva", email: "nadeesha.silva@uom.lk", department: "Computer Science and Engineering", designation: "Lecturer", accountStatus: "active", profileStatus: "active" },
];

const ADMINISTRATORS: AdministratorAccount[] = [
  { userId: "user-admin-1", fullName: "Dr. Sunimal Rathnayake", email: "sunimal@uom.lk", department: "Computer Science and Engineering", administrativeScope: "Faculty", accountStatus: "active", profileStatus: "active" },
];

export const MOCK_USER_DIRECTORY: UserDirectoryData = {
  students: STUDENTS,
  lecturers: LECTURERS,
  administrators: ADMINISTRATORS,
};

export const MOCK_ACADEMIC_DATA: AcademicData = {
  sourceConnectionStatus: "not_configured",
  courses: [
    { courseId: "course-cs3203", courseCode: "CS3203", courseName: "Database Systems", department: "Computer Science and Engineering", credits: 3, status: "active" },
    { courseId: "course-cs2101", courseCode: "CS2101", courseName: "Introduction to Programming", department: "Computer Science and Engineering", credits: 4, status: "active" },
    { courseId: "course-cs4301", courseCode: "CS4301", courseName: "Artificial Intelligence", department: "Computer Science and Engineering", credits: 3, status: "active" },
    { courseId: "course-cs5230", courseCode: "CS5230", courseName: "Data Mining", department: "Computer Science and Engineering", credits: 3, status: "active" },
  ],
  offerings: [
    { offeringId: "offering-1", courseCode: "CS3203", courseName: "Database Systems", semesterLabel: "Semester 2 · 2026", batchYear: 2023, courseType: "Lecture", attendanceThresholdPercent: 80, enrolledCount: 92, status: "active" },
    { offeringId: "offering-2", courseCode: "CS2101", courseName: "Introduction to Programming", semesterLabel: "Semester 2 · 2026", batchYear: 2023, courseType: "Lecture", attendanceThresholdPercent: 80, enrolledCount: 75, status: "active" },
    { offeringId: "offering-3", courseCode: "CS4301", courseName: "Artificial Intelligence", semesterLabel: "Semester 2 · 2026", batchYear: 2023, courseType: "Lecture", attendanceThresholdPercent: 80, enrolledCount: 68, status: "active" },
  ],
  timetable: [
    { id: "tt-1", courseCode: "CS3203", courseName: "Database Systems", day: "Tuesday", timeRange: "10:00–11:30", room: "LT-301", lecturerName: "Prof. Dulani Meedeniya" },
    { id: "tt-2", courseCode: "CS2101", courseName: "Introduction to Programming", day: "Tuesday", timeRange: "13:00–14:30", room: "LT-202", lecturerName: "Prof. Dulani Meedeniya" },
    { id: "tt-3", courseCode: "CS4301", courseName: "Artificial Intelligence", day: "Tuesday", timeRange: "15:00–16:30", room: "LT-204", lecturerName: "Prof. Dulani Meedeniya" },
  ],
  enrolments: [
    { enrolmentId: "enr-1", studentName: "Oshadha Wijayarathne", registrationNumber: "230714A", courseCode: "CS3203", semesterLabel: "Semester 2 · 2026", enrolmentStatus: "enrolled" },
    { enrolmentId: "enr-2", studentName: "Benjamin Ong", registrationNumber: "230738B", courseCode: "CS3203", semesterLabel: "Semester 2 · 2026", enrolmentStatus: "enrolled" },
    { enrolmentId: "enr-3", studentName: "Chloe Lim", registrationNumber: "230741C", courseCode: "CS2101", semesterLabel: "Semester 2 · 2026", enrolmentStatus: "enrolled" },
  ],
};

export const MOCK_REFERENCE_FACES: ReferenceFaceRecord[] = [
  { studentId: "user-stu-1", studentName: "Oshadha Wijayarathne", registrationNumber: "230714A", embeddingGenerationStatus: "generated", readinessStatus: "passed", generatedAtLabel: "12 Jul 2026", readinessCheckedAtLabel: "12 Jul 2026" },
  { studentId: "user-stu-2", studentName: "Benjamin Ong", registrationNumber: "230738B", embeddingGenerationStatus: "generated", readinessStatus: "passed", generatedAtLabel: "10 Jul 2026", readinessCheckedAtLabel: "10 Jul 2026" },
  { studentId: "user-stu-3", studentName: "Chloe Lim", registrationNumber: "230741C", embeddingGenerationStatus: "pending", readinessStatus: "not_checked", generatedAtLabel: null, readinessCheckedAtLabel: null },
  { studentId: "user-stu-4", studentName: "Fiona Chang", registrationNumber: "230799F", embeddingGenerationStatus: "failed", readinessStatus: "failed", generatedAtLabel: null, readinessCheckedAtLabel: "9 Jul 2026" },
  { studentId: "user-stu-5", studentName: "Aisha Rahman", registrationNumber: "230876A", embeddingGenerationStatus: "generated", readinessStatus: "expired", generatedAtLabel: "2 Jan 2026", readinessCheckedAtLabel: "2 Jan 2026" },
];

export const MOCK_INSTITUTION_REPORTS: InstitutionReportsData = {
  summary: {
    overallAttendancePercent: 87.4,
    totalSessionsCompleted: 612,
    totalStudents: 3984,
    totalLecturers: 126,
    studentsAtRiskCount: 143,
  },
  attendanceTrend: [
    { label: "W1", attendanceRate: 84 },
    { label: "W2", attendanceRate: 86 },
    { label: "W3", attendanceRate: 88 },
    { label: "W4", attendanceRate: 85 },
    { label: "W5", attendanceRate: 90 },
    { label: "W6", attendanceRate: 89 },
    { label: "W7", attendanceRate: 91 },
  ],
  attendanceByFaculty: [
    { facultyName: "Engineering", attendanceRatePercent: 89 },
    { facultyName: "Architecture", attendanceRatePercent: 85 },
    { facultyName: "Business", attendanceRatePercent: 82 },
  ],
  atRiskCourses: [
    { courseCode: "CS6101", courseName: "Cybersecurity Fundamentals", attendanceRatePercent: 68 },
    { courseCode: "CS5230", courseName: "Data Mining", attendanceRatePercent: 71 },
  ],
};

export const MOCK_AUDIT_LOG: AuditLogEntry[] = [
  { id: "audit-1", occurredAtLabel: "16 Aug 2026, 10:12", actorName: "Prof. Dulani Meedeniya", actorRole: "lecturer", action: "Approved attendance override", entityType: "attendance_record", entityLabel: "Oshadha Wijayarathne · CS3203", outcome: "success" },
  { id: "audit-2", occurredAtLabel: "16 Aug 2026, 10:00", actorName: "Prof. Dulani Meedeniya", actorRole: "lecturer", action: "Opened attendance session", entityType: "session", entityLabel: "CS3203 · 10:00 lecture", outcome: "success" },
  { id: "audit-3", occurredAtLabel: "15 Aug 2026, 16:45", actorName: "Dr. Sunimal Rathnayake", actorRole: "administrator", action: "Updated classroom geofence", entityType: "classroom", entityLabel: "AI-Lab-02", outcome: "success" },
  { id: "audit-4", occurredAtLabel: "15 Aug 2026, 09:30", actorName: "Dr. Sunimal Rathnayake", actorRole: "administrator", action: "Updated attendance policy", entityType: "policy", entityLabel: "Face confidence threshold → 75%", outcome: "success" },
];
