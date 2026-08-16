// MOCK DATA — no administrator-facing backend endpoints exist yet (see repo inspection
// notes). Stage 4 introduces services/admin.ts behind the same shapes
// (apps/web/src/types/admin.ts) so real API responses drop in without page rewrites.
import { AdminDashboardData } from "@/types/admin";

export const MOCK_ADMIN_DASHBOARD: AdminDashboardData = {
  summary: {
    activeUsersCount: 4286,
    configuredClassroomsCount: 28,
    activeGeofencesCount: 24,
    academicSourceStatusLabel: "Connected",
    lastSyncLabel: "Last sync 07:00",
    policyAlertsCount: 2,
  },
  classrooms: [
    { classroomId: "room-cs-lab-01", room: "CS-Lab-01", building: "CSE Building", defaultGeofenceRadiusMeters: 25, assignedCoursesCount: 3, status: "active" },
    { classroomId: "room-lt-301", room: "LT-301", building: "Sumanadasa Building", defaultGeofenceRadiusMeters: 30, assignedCoursesCount: 4, status: "active" },
    { classroomId: "room-lt-204", room: "LT-204", building: "CSE Building", defaultGeofenceRadiusMeters: 30, assignedCoursesCount: 2, status: "active" },
    { classroomId: "room-ai-lab-02", room: "AI-Lab-02", building: "Innovation Hub", defaultGeofenceRadiusMeters: 20, assignedCoursesCount: 2, status: "needs_review" },
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
    { id: "sync-1", time: "07:00", title: "Course catalogue", detail: "428 course records received", status: "current" },
    { id: "sync-2", time: "07:00", title: "Student enrolments", detail: "3,984 active enrolments received", status: "current" },
    { id: "sync-3", time: "07:01", title: "Lecturer assignments", detail: "126 assignments validated", status: "current" },
    { id: "sync-4", time: "07:02", title: "Timetable entries", detail: "2 records require correction", status: "review" },
  ],
};
