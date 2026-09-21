import { beforeEach, describe, expect, it, vi } from "vitest";
import { revalidatePath } from "next/cache";
import { CoreBackendError } from "@/lib/api/coreBackend";
import { cancelLecturerSession, closeLecturerSession, createLecturerSession } from "@/lib/api/lecturer";
import { cancelSession, closeSession, createSession, type CreateSessionInput } from "@/app/actions/sessions";
import {
  mockCloseSessionWithSummary,
  mockCloseSessionWithoutSummary,
  mockCancelSessionResponse,
} from "@/mocks/fixtures/lecturerLive";

vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));
vi.mock("@/lib/api/coreBackend", () => ({
  CoreBackendError: class CoreBackendError extends Error {
    constructor(message: string, public status: number) { super(message); }
  },
}));
vi.mock("@/lib/api/lecturer", () => ({
  createLecturerSession: vi.fn(), closeLecturerSession: vi.fn(), cancelLecturerSession: vi.fn(),
}));

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

describe("session close and cancellation", () => {
  beforeEach(() => vi.clearAllMocks());

  it("returns the close summary and refreshes lecturer views", async () => {
    vi.mocked(closeLecturerSession).mockResolvedValue(mockCloseSessionWithSummary);
    expect(await closeSession("session-1")).toEqual({
      ok: true, finalization: mockCloseSessionWithSummary.finalization,
    });
    expect(revalidatePath).toHaveBeenCalledWith("/lecturer/sessions/session-1");
    expect(revalidatePath).toHaveBeenCalledWith("/lecturer/sessions");
    expect(revalidatePath).toHaveBeenCalledWith("/lecturer/dashboard");
  });

  it("preserves a null finalization without inventing counts", async () => {
    vi.mocked(closeLecturerSession).mockResolvedValue(mockCloseSessionWithoutSummary);
    expect(await closeSession("session-1")).toEqual({ ok: true, finalization: null });
  });

  it("validates and trims a cancellation reason before writing", async () => {
    expect(await cancelSession("session-1", "  x  ")).toEqual({
      ok: false, error: "Reason must be between 3 and 500 characters.",
    });
    expect(cancelLecturerSession).not.toHaveBeenCalled();

    vi.mocked(cancelLecturerSession).mockResolvedValue(mockCancelSessionResponse);
    expect(await cancelSession("session-1", "  Lecturer unavailable  ")).toEqual({ ok: true });
    expect(cancelLecturerSession).toHaveBeenCalledWith("session-1", "Lecturer unavailable");
    expect(revalidatePath).toHaveBeenCalledWith("/lecturer/sessions/session-1");
  });

  it("reports a cancellation conflict without refreshing stale views", async () => {
    vi.mocked(cancelLecturerSession).mockRejectedValue(new CoreBackendError(
      "A closed session cannot be cancelled.", 409, "/cancel",
    ));
    expect(await cancelSession("session-1", "Lecturer unavailable")).toEqual({
      ok: false, error: "A closed session cannot be cancelled.",
    });
    expect(revalidatePath).not.toHaveBeenCalled();
  });
});
