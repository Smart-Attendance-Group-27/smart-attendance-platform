import "server-only";
import { mockDelay } from "@/lib/mockDelay";
import { MOCK_ADMIN_DASHBOARD } from "@/mocks/admin";
import { AdminDashboardData } from "@/types/admin";

// Backed by mock data (apps/web/src/mocks/admin.ts) — no administrator-facing backend
// endpoints exist yet. See lecturerService.ts for the same pattern.

export async function getAdminDashboard(): Promise<AdminDashboardData> {
  return mockDelay(MOCK_ADMIN_DASHBOARD);
}
