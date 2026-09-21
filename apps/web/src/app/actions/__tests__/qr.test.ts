import { beforeEach, describe, expect, it, vi } from "vitest";
import { revalidatePath } from "next/cache";
import { CoreBackendError } from "@/lib/api/coreBackend";
import { voidLecturerQrBatch } from "@/lib/api/lecturer";
import { isWebMockMode } from "@/lib/api/mode";
import { voidQrBatch } from "@/app/actions/qr";

vi.mock("server-only", () => ({}));
vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));
vi.mock("@/lib/api/coreBackend", () => ({
  CoreBackendError: class extends Error {
    constructor(message: string, public status: number) { super(message); }
  },
}));
vi.mock("@/lib/api/lecturer", () => ({ voidLecturerQrBatch: vi.fn() }));
vi.mock("@/lib/api/mode", () => ({ isWebMockMode: vi.fn(() => false) }));

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(isWebMockMode).mockReturnValue(false);
});

describe("voidQrBatch", () => {
  it("sends a trimmed reason and refreshes the QR and session views", async () => {
    vi.mocked(voidLecturerQrBatch).mockResolvedValue({} as never);
    expect(await voidQrBatch("session-1", "batch-1", "  Created by mistake  ")).toEqual({ ok: true });
    expect(voidLecturerQrBatch).toHaveBeenCalledWith("session-1", "batch-1", "Created by mistake");
    expect(revalidatePath).toHaveBeenCalledWith("/lecturer/sessions/session-1/qr");
    expect(revalidatePath).toHaveBeenCalledWith("/lecturer/sessions/session-1");
  });

  it("rejects an empty reason before writing", async () => {
    expect(await voidQrBatch("session-1", "batch-1", "  ")).toMatchObject({ ok: false });
    expect(voidLecturerQrBatch).not.toHaveBeenCalled();
  });

  it("returns a closed-session conflict without revalidating", async () => {
    vi.mocked(voidLecturerQrBatch).mockRejectedValue(new CoreBackendError(
      "This session no longer permits voiding QR batches.", 409, "/void",
    ));
    expect(await voidQrBatch("session-1", "batch-1", "Mistake")).toMatchObject({ ok: false });
    expect(revalidatePath).not.toHaveBeenCalled();
  });

  it("does not write in mock preview", async () => {
    vi.mocked(isWebMockMode).mockReturnValue(true);
    expect(await voidQrBatch("session-1", "batch-1", "Mistake")).toEqual({
      ok: false, error: "Mock preview is read-only.",
    });
    expect(voidLecturerQrBatch).not.toHaveBeenCalled();
  });
});
