import { beforeEach, describe, expect, it, vi } from "vitest";
import { revalidatePath } from "next/cache";
import { postManualReviewDecision } from "@/lib/api/lecturer";
import { submitReviewDecision, type ReviewDecisionInput } from "@/app/actions/review";

vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));
vi.mock("@/lib/api/lecturer", () => ({ postManualReviewDecision: vi.fn() }));

describe("submitReviewDecision", () => {
  beforeEach(() => vi.clearAllMocks());

  it("sends the lecturer's explicit Late choice and trimmed reason", async () => {
    await submitReviewDecision("attempt-1", {
      decision: "approve",
      attendanceStatus: "late",
      reason: "  Verified with the lecturer  ",
    });

    expect(postManualReviewDecision).toHaveBeenCalledWith("attempt-1", {
      decision: "approve",
      attendanceStatus: "late",
      reason: "Verified with the lecturer",
    });
    expect(revalidatePath).toHaveBeenCalledWith("/lecturer/review");
    expect(revalidatePath).toHaveBeenCalledWith("/lecturer/dashboard");
  });

  it("rejects without sending an attendance status", async () => {
    await submitReviewDecision("attempt-2", {
      decision: "reject",
      reason: "Evidence did not pass",
    });

    expect(postManualReviewDecision).toHaveBeenCalledWith("attempt-2", {
      decision: "reject",
      reason: "Evidence did not pass",
    });
  });

  it.each([
    { decision: "approve", reason: "Valid reason" },
    { decision: "reject", attendanceStatus: "present", reason: "Valid reason" },
    { decision: "retry", reason: "Valid reason" },
    { decision: "approve", attendanceStatus: "present", reason: "  " },
  ])("rejects an invalid C16 request before calling the backend: %j", async (input) => {
    await expect(submitReviewDecision("attempt-1", input as ReviewDecisionInput)).rejects.toThrow();
    expect(postManualReviewDecision).not.toHaveBeenCalled();
  });
});
