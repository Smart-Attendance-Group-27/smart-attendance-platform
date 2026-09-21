import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { coreBackendFetch } from "@/lib/api/coreBackend";
import { getLecturerQrBatches, putManualAttendance } from "@/lib/api/lecturer";
import { getSessionDetail, getSessionList, getSessionQrBatches } from "@/services/lecturerService";
import { initialCheckInDisplay, liveFinalStatusDisplay, qrProgressLabel } from "@/lib/status";
import { QrBatchParticipationTable } from "@/components/lecturer/QrBatchParticipationTable";

vi.mock("server-only", () => ({}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));
vi.mock("@/lib/auth/dal", () => ({ getCurrentUser: vi.fn(async () => ({ name: "Lecturer" })) }));
vi.mock("@/lib/api/coreBackend", () => ({ coreBackendFetch: vi.fn() }));

beforeEach(() => {
  vi.unstubAllEnvs();
  vi.clearAllMocks();
});

describe("lecturer live view", () => {
  it("maps C12/C13 mock states without inventing final attendance", async () => {
    vi.stubEnv("WEB_API_MODE", "mock");
    const detail = await getSessionDetail("mock-live-session");
    expect(detail).not.toBeNull();
    expect(detail?.summary).toMatchObject({
      checkedInCount: 1, lateCheckedInCount: 1,
      notCheckedInCount: 2, failedVerificationCount: 1, manualCount: 1,
    });
    const first = detail!.students[0];
    expect(initialCheckInDisplay(first).label).toBe("Checked in");
    expect(qrProgressLabel(first)).toBe("1/2");
    expect(liveFinalStatusDisplay(first, detail!.status).label).toBe("Awaiting final result");

    const manual = detail!.students[1];
    expect(initialCheckInDisplay(manual).label).toBe("Checked in late");
    expect(manual.recordSource).toBe("manual");
    expect(liveFinalStatusDisplay(manual, detail!.status).label).toBe("Present");
    expect(qrProgressLabel(detail!.students[2])).toBe("—");
    expect(initialCheckInDisplay(detail!.students[3]).label).toBe("Failed verification");
    expect(initialCheckInDisplay(detail!.students[4]).label).toBe("Not started");

    const sessions = await getSessionList();
    expect(sessions.find((item) => item.sessionId === "mock-live-session"))
      .toMatchObject({ checkedInCount: 1, lateCheckedInCount: 1 });
  });

  it("loads C09 in real mode and renders newest participation first", async () => {
    vi.stubEnv("WEB_API_MODE", "real");
    const batches = [{
      qrSessionId: "batch-1", mode: "static" as const, status: "closed",
      activatedAt: "2026-09-20T10:00:00Z", deactivatedAt: "2026-09-20T10:05:00Z",
      expiresAt: "2026-09-20T10:10:00Z", voided: false, voidReason: null,
      requiredStudentCount: 3, passedStudentCount: 2,
    }, {
      qrSessionId: "batch-2", mode: "dynamic" as const, status: "active",
      activatedAt: "2026-09-20T10:10:00Z", deactivatedAt: null,
      expiresAt: "2026-09-20T10:30:00Z", voided: false, voidReason: null,
      requiredStudentCount: 5, passedStudentCount: 4,
    }];
    vi.mocked(coreBackendFetch).mockResolvedValue(batches);
    expect(await getLecturerQrBatches("session one")).toEqual(batches);
    expect(coreBackendFetch).toHaveBeenCalledWith(
      "/api/v1/lecturers/me/attendance-sessions/session%20one/qr-batches",
    );

    render(<QrBatchParticipationTable batches={batches} sessionId="session one" canVoid={false} />);
    const rows = screen.getAllByRole("row");
    expect(rows[1]).toHaveTextContent("batch-2");
    expect(rows[1]).toHaveTextContent("4/5");
    expect(rows[2]).toHaveTextContent("batch-1");
  });

  it("uses C09 fixtures without calling the backend in mock mode", async () => {
    vi.stubEnv("WEB_API_MODE", "mock");
    const batches = await getSessionQrBatches("mock-live-session");
    expect(batches).toHaveLength(2);
    expect(batches[0]).toMatchObject({ requiredStudentCount: 2, passedStudentCount: 1 });
    expect(coreBackendFetch).not.toHaveBeenCalled();
  });

  it("sends the C11 manual attendance PUT to the student's roster URL", async () => {
    vi.stubEnv("WEB_API_MODE", "real");
    vi.mocked(coreBackendFetch).mockResolvedValue({ status: "late", source: "manual" });
    await putManualAttendance("session one", "student/two", {
      status: "late", reason: "Lecturer confirmed arrival",
    });
    expect(coreBackendFetch).toHaveBeenCalledWith(
      "/api/v1/lecturers/me/attendance-sessions/session%20one/students/student%2Ftwo/attendance",
      { method: "PUT", body: { status: "late", reason: "Lecturer confirmed arrival" } },
    );
  });
});
