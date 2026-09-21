import { beforeEach, describe, expect, it, vi } from "vitest";
import { revalidatePath } from "next/cache";
import { putAttendancePolicy } from "@/lib/api/admin";
import { isWebMockMode } from "@/lib/api/mode";
import { saveAttendancePolicy } from "@/app/actions/policies";

vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));
vi.mock("server-only", () => ({}));
vi.mock("@/lib/api/admin", () => ({ putAttendancePolicy: vi.fn() }));
vi.mock("@/lib/api/mode", () => ({ isWebMockMode: vi.fn(() => false) }));

const validPolicy = {
  checkInWindowMinutes: 15,
  lateThresholdMinutes: 5,
  qrDefaultValidityMinutes: 10,
  faceConfidenceThresholdPercent: 75,
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(isWebMockMode).mockReturnValue(false);
});

describe("saveAttendancePolicy", () => {
  it("saves valid C17 values and refreshes both administrator views", async () => {
    vi.mocked(putAttendancePolicy).mockResolvedValue({ ...validPolicy, updatedAt: "now", updatedByName: "Admin" });
    expect(await saveAttendancePolicy(validPolicy)).toEqual({ ok: true });
    expect(putAttendancePolicy).toHaveBeenCalledWith(validPolicy);
    expect(revalidatePath).toHaveBeenCalledWith("/admin/policies");
    expect(revalidatePath).toHaveBeenCalledWith("/admin/dashboard");
  });

  it("rejects a late threshold beyond the window", async () => {
    expect(await saveAttendancePolicy({ ...validPolicy, lateThresholdMinutes: 16 })).toMatchObject({ ok: false });
    expect(putAttendancePolicy).not.toHaveBeenCalled();
  });

  it("keeps the mock preview read-only", async () => {
    vi.mocked(isWebMockMode).mockReturnValue(true);
    expect(await saveAttendancePolicy(validPolicy)).toEqual({ ok: false, error: "Mock preview is read-only." });
    expect(putAttendancePolicy).not.toHaveBeenCalled();
  });
});
