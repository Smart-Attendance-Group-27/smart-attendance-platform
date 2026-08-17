import "server-only";
import { mockDelay } from "@/lib/mockDelay";
import {
  MOCK_ACADEMIC_DATA,
  MOCK_ADMIN_DASHBOARD,
  MOCK_AUDIT_LOG,
  MOCK_INSTITUTION_REPORTS,
  MOCK_REFERENCE_FACES,
  MOCK_USER_DIRECTORY,
} from "@/mocks/admin";
import {
  AcademicData,
  AdminDashboardData,
  AuditLogEntry,
  InstitutionReportsData,
  ReferenceFaceRecord,
  UserDirectoryData,
} from "@/types/admin";

// Backed by mock data (apps/web/src/mocks/admin.ts) — no administrator-facing backend
// endpoints exist yet. See lecturerService.ts for the same pattern.

export async function getAdminDashboard(): Promise<AdminDashboardData> {
  return mockDelay(MOCK_ADMIN_DASHBOARD);
}

export async function getUserDirectory(): Promise<UserDirectoryData> {
  return mockDelay(MOCK_USER_DIRECTORY);
}

export async function getAcademicData(): Promise<AcademicData> {
  return mockDelay(MOCK_ACADEMIC_DATA);
}

export async function getReferenceFaces(): Promise<ReferenceFaceRecord[]> {
  return mockDelay(MOCK_REFERENCE_FACES);
}

export async function getInstitutionReports(): Promise<InstitutionReportsData> {
  return mockDelay(MOCK_INSTITUTION_REPORTS);
}

export async function getAuditLog(): Promise<AuditLogEntry[]> {
  return mockDelay(MOCK_AUDIT_LOG);
}
