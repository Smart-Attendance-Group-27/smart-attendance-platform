import { beforeEach, describe, expect, it, vi } from "vitest";
import { revalidatePath } from "next/cache";
import { CoreBackendError } from "@/lib/api/coreBackend";
import { decideAdminCorrectionRequest } from "@/lib/api/admin";
import { submitLecturerCorrectionRequest } from "@/lib/api/lecturer";
import { decideCorrectionRequest, submitCorrectionRequest } from "@/app/actions/corrections";

vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));
vi.mock("@/lib/api/coreBackend", () => ({
  CoreBackendError: class CoreBackendError extends Error {
    constructor(message: string, public status: number) { super(message); }
  },
}));
vi.mock("@/lib/api/lecturer", () => ({ submitLecturerCorrectionRequest: vi.fn() }));
vi.mock("@/lib/api/admin", () => ({ decideAdminCorrectionRequest: vi.fn() }));

const valid = {
  requestType: "course_data" as const,
  category: "enrolment" as const,
  courseOfferingId: "offering-1",
  description: "  Three students are missing from the list.  ",
};

describe("submitCorrectionRequest", () => {
  beforeEach(() => vi.clearAllMocks());

  it("sends a trimmed course request and refreshes the page", async () => {
    vi.mocked(submitLecturerCorrectionRequest).mockResolvedValue({} as Awaited<ReturnType<typeof submitLecturerCorrectionRequest>>);
    expect(await submitCorrectionRequest(valid)).toEqual({ ok: true });
    expect(submitLecturerCorrectionRequest).toHaveBeenCalledWith({
      requestType: "course_data",
      category: "enrolment",
      courseOfferingId: "offering-1",
      timetableEntryId: undefined,
      description: "Three students are missing from the list.",
    });
    expect(revalidatePath).toHaveBeenCalledWith("/lecturer/courses");
  });

  it("sends only the timetable entry for a timetable request", async () => {
    vi.mocked(submitLecturerCorrectionRequest).mockResolvedValue({} as Awaited<ReturnType<typeof submitLecturerCorrectionRequest>>);
    await submitCorrectionRequest({
      requestType: "timetable",
      category: "timetable_room",
      courseOfferingId: "ignored",
      timetableEntryId: "entry-1",
      description: "The room shown is not the one we use.",
    });
    expect(submitLecturerCorrectionRequest).toHaveBeenCalledWith(
      expect.objectContaining({ courseOfferingId: undefined, timetableEntryId: "entry-1" }),
    );
  });

  it.each([
    [{ description: "short" }],
    [{ courseOfferingId: undefined }],
    [{ category: "timetable_room" as const }],
  ])("rejects invalid input before calling the backend", async (override) => {
    const result = await submitCorrectionRequest({ ...valid, ...override });
    expect(result.ok).toBe(false);
    expect(submitLecturerCorrectionRequest).not.toHaveBeenCalled();
  });

  it("surfaces a client error message from the backend", async () => {
    vi.mocked(submitLecturerCorrectionRequest).mockRejectedValue(
      new CoreBackendError("That course or timetable entry is not assigned to you.", 404, "/x"),
    );
    expect(await submitCorrectionRequest(valid)).toEqual({
      ok: false, error: "That course or timetable entry is not assigned to you.",
    });
    expect(revalidatePath).not.toHaveBeenCalled();
  });

  it("hides server failures behind a generic message", async () => {
    vi.mocked(submitLecturerCorrectionRequest).mockRejectedValue(new CoreBackendError("boom", 500, "/x"));
    expect(await submitCorrectionRequest(valid)).toEqual({
      ok: false, error: "Couldn't submit the request. Please try again.",
    });
  });
});

describe("decideCorrectionRequest", () => {
  beforeEach(() => vi.clearAllMocks());

  it("sends a trimmed decision and refreshes both affected pages", async () => {
    vi.mocked(decideAdminCorrectionRequest).mockResolvedValue({} as Awaited<ReturnType<typeof decideAdminCorrectionRequest>>);

    expect(await decideCorrectionRequest("req-1", "pending", "approved", "  Will fix it.  ")).toEqual({ ok: true });

    expect(decideAdminCorrectionRequest).toHaveBeenCalledWith("req-1", { decision: "approved", note: "Will fix it." });
    expect(revalidatePath).toHaveBeenCalledWith("/admin/corrections");
    expect(revalidatePath).toHaveBeenCalledWith("/lecturer/courses");
  });

  it.each([
    ["pending", "resolved", "ok note"],
    ["approved", "approved", "ok note"],
    ["rejected", "approved", "ok note"],
    ["resolved", "resolved", "ok note"],
  ] as const)("refuses %s -> %s without calling the backend", async (status, decision, note) => {
    const result = await decideCorrectionRequest("req-1", status, decision, note);

    expect(result.ok).toBe(false);
    expect(decideAdminCorrectionRequest).not.toHaveBeenCalled();
  });

  it("requires a reason to reject", async () => {
    const result = await decideCorrectionRequest("req-1", "pending", "rejected", "  ");

    expect(result).toEqual({ ok: false, error: "Give the lecturer a reason for rejecting the request." });
    expect(decideAdminCorrectionRequest).not.toHaveBeenCalled();
  });

  it("shows a backend conflict message and hides server failures", async () => {
    vi.mocked(decideAdminCorrectionRequest).mockRejectedValueOnce(new CoreBackendError("Already decided.", 409, "/x"));
    expect(await decideCorrectionRequest("req-1", "pending", "approved", "")).toEqual({ ok: false, error: "Already decided." });

    vi.mocked(decideAdminCorrectionRequest).mockRejectedValueOnce(new CoreBackendError("boom", 500, "/x"));
    expect(await decideCorrectionRequest("req-1", "pending", "approved", "")).toEqual({
      ok: false,
      error: "Couldn't save the decision. Please try again.",
    });
  });
});
