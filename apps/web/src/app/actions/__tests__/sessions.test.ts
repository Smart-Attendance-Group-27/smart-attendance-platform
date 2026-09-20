import { beforeEach, describe, expect, it, vi } from "vitest";
import { createLecturerSession } from "@/lib/api/lecturer";
import { createSession, type CreateSessionInput } from "@/app/actions/sessions";

vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));
vi.mock("@/lib/api/coreBackend", () => ({ CoreBackendError: class CoreBackendError extends Error {} }));
vi.mock("@/lib/api/lecturer", () => ({ createLecturerSession: vi.fn() }));

describe("createSession", () => {
  beforeEach(() => vi.clearAllMocks());

  it("always requires geofence even if a caller supplies false", async () => {
    vi.mocked(createLecturerSession).mockResolvedValue({ id: "session-1" } as Awaited<ReturnType<typeof createLecturerSession>>);
    const input = {
      timetableEntryId: "entry-1",
      sessionTitle: "Week 6 lecture",
      scheduledStartAt: "2026-09-20T09:00:00.000Z",
      scheduledEndAt: "2026-09-20T10:00:00.000Z",
      requiresFaceVerification: true,
      requiresQr: false,
      requiresGeofence: false,
    } as CreateSessionInput;

    expect(await createSession(input)).toEqual({ ok: true, sessionId: "session-1" });
    expect(createLecturerSession).toHaveBeenCalledWith(expect.objectContaining({ requiresGeofence: true }));
  });
});
