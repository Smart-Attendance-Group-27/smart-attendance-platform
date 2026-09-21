import { beforeEach, describe, expect, it, vi } from "vitest";
import { revalidatePath } from "next/cache";
import { CoreBackendError } from "@/lib/api/coreBackend";
import { isWebMockMode } from "@/lib/api/mode";
import { putManualAttendance } from "@/lib/api/lecturer";
import { setStudentAttendance } from "@/app/actions/attendance";

vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));
vi.mock("@/lib/api/coreBackend", () => ({
  CoreBackendError: class extends Error {
    constructor(message: string, public status: number) { super(message); }
  },
}));
vi.mock("@/lib/api/mode", () => ({ isWebMockMode: vi.fn(() => false) }));
vi.mock("@/lib/api/lecturer", () => ({ putManualAttendance: vi.fn() }));

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(isWebMockMode).mockReturnValue(false);
});

describe("setStudentAttendance", () => {
  it.each(["present", "late", "absent"] as const)(
    "writes %s with a trimmed reason and refreshes lecturer views",
    async (status) => {
      vi.mocked(putManualAttendance).mockResolvedValue({
        sessionId: "session-1", studentId: "student-1", status,
        source: "manual", reason: "Verified by lecturer", recordedBy: "lecturer-1",
        updatedAt: "2026-09-21T10:00:00Z",
      });
      expect(await setStudentAttendance("session-1", "student-1", {
        status, reason: "  Verified by lecturer  ",
      })).toEqual({ ok: true, status });
      expect(putManualAttendance).toHaveBeenCalledWith("session-1", "student-1", {
        status, reason: "Verified by lecturer",
      });
      expect(revalidatePath).toHaveBeenCalledWith("/lecturer/sessions/session-1");
      expect(revalidatePath).toHaveBeenCalledWith("/lecturer/dashboard");
      vi.clearAllMocks();
    },
  );

  it("rejects an invalid reason before writing", async () => {
    expect(await setStudentAttendance("session-1", "student-1", {
      status: "present", reason: "  x  ",
    })).toEqual({ ok: false, error: "Reason must be between 3 and 500 characters." });
    expect(putManualAttendance).not.toHaveBeenCalled();
  });

  it("reports a conflict without revalidating", async () => {
    vi.mocked(putManualAttendance).mockRejectedValue(new CoreBackendError(
      "SESSION_CANCELLED", 409, "/attendance",
    ));
    expect(await setStudentAttendance("session-1", "student-1", {
      status: "late", reason: "Confirmed in class",
    })).toMatchObject({ ok: false, error: expect.stringContaining("cancellation") });
    expect(revalidatePath).not.toHaveBeenCalled();
  });

  it("does not write from mock preview", async () => {
    vi.mocked(isWebMockMode).mockReturnValue(true);
    expect(await setStudentAttendance("session-1", "student-1", {
      status: "absent", reason: "No attendance evidence",
    })).toEqual({ ok: false, error: "Mock preview is read-only." });
    expect(putManualAttendance).not.toHaveBeenCalled();
  });
});
