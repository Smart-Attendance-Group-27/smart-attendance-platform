import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReviewWorkspace } from "@/components/lecturer/ReviewWorkspace";
import { submitReviewDecision } from "@/app/actions/review";
import type { ReviewCase } from "@/types/lecturer";

vi.mock("@/app/actions/review", () => ({ submitReviewDecision: vi.fn() }));

const reviewCase: ReviewCase = {
  caseId: "attempt-1",
  studentId: "student-1",
  studentIndex: "230001",
  studentName: "Test Student",
  studentProgramme: "Engineering",
  courseCode: "CS101",
  issueType: "low_confidence_face_match",
  issueLabel: "Low-confidence face match",
  faceScorePercent: 48,
  faceThresholdPercent: 70,
  geofenceResult: "within_radius",
  time: "09:10",
  status: "pending",
  livenessPassed: true,
  geofenceDistanceMeters: 10,
  qrEventLabel: "Not required",
  reviewReason: "Face match below threshold",
};

const showModal = HTMLDialogElement.prototype.showModal;
const close = HTMLDialogElement.prototype.close;

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute("open"); };
});
afterAll(() => {
  HTMLDialogElement.prototype.showModal = showModal;
  HTMLDialogElement.prototype.close = close;
});
beforeEach(() => vi.clearAllMocks());

describe("ReviewWorkspace", () => {
  it("requires an explicit status and reason before approving", async () => {
    const user = userEvent.setup();
    render(<ReviewWorkspace initialCases={[reviewCase]} />);

    expect(screen.queryByRole("button", { name: "Request retry" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Escalate" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Approve attendance" }));
    const dialog = screen.getByRole("dialog");
    const approve = within(dialog).getByRole("button", { name: "Approve" });
    expect(approve).toBeDisabled();

    await user.click(within(dialog).getByRole("radio", { name: "Late" }));
    await user.type(within(dialog).getByLabelText("Reason"), "Lecturer confirmed late arrival");
    await user.click(approve);

    expect(submitReviewDecision).toHaveBeenCalledWith("attempt-1", {
      decision: "approve",
      attendanceStatus: "late",
      reason: "Lecturer confirmed late arrival",
    });
  });

  it("rejects with a reason and no attendance status", async () => {
    const user = userEvent.setup();
    render(<ReviewWorkspace initialCases={[reviewCase]} />);

    await user.click(screen.getByRole("button", { name: "Reject" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).queryByRole("radio")).not.toBeInTheDocument();
    await user.type(within(dialog).getByLabelText("Reason"), "Evidence was invalid");
    await user.click(within(dialog).getByRole("button", { name: "Reject" }));

    expect(submitReviewDecision).toHaveBeenCalledWith("attempt-1", {
      decision: "reject",
      reason: "Evidence was invalid",
    });
  });
});
