import { beforeEach, describe, expect, it, vi } from "vitest";
import { revalidatePath } from "next/cache";
import { CoreBackendError } from "@/lib/api/coreBackend";
import { submitLecturerCorrectionRequest } from "@/lib/api/lecturer";
import { submitCorrectionRequest } from "@/app/actions/corrections";

vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));
vi.mock("@/lib/api/coreBackend", () => ({
  CoreBackendError: class CoreBackendError extends Error {
    constructor(message: string, public status: number) { super(message); }
  },
}));
vi.mock("@/lib/api/lecturer", () => ({ submitLecturerCorrectionRequest: vi.fn() }));

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
