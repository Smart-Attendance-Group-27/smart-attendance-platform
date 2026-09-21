import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ManualAttendanceDialog } from "@/components/lecturer/ManualAttendanceDialog";
import { setStudentAttendance } from "@/app/actions/attendance";
import type { LiveSessionStudentRow } from "@/types/lecturer";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));
vi.mock("@/app/actions/attendance", () => ({ setStudentAttendance: vi.fn() }));

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

const student: LiveSessionStudentRow = {
  studentId: "student-1", studentIndex: "2307001", fullName: "Nimali Perera",
  attemptStatus: "checked_in", initialCheckInStatus: "checked_in",
  faceStatus: "passed", failureReason: null, checkedInAt: "2026-09-21T10:00:00Z",
  qrRequiredCount: 1, qrPassedCount: 1, finalStatus: null,
  recordSource: null, manualReason: null, recordUpdatedAt: null, reviewStatus: null,
};

describe("ManualAttendanceDialog", () => {
  it("sets Late with a reason and refreshes the roster", async () => {
    const user = userEvent.setup();
    vi.mocked(setStudentAttendance).mockResolvedValue({ ok: true, status: "late" });
    render(<ManualAttendanceDialog sessionId="session-1" student={student} />);
    await user.click(screen.getByRole("button", { name: "Set attendance" }));
    const dialog = screen.getByRole("dialog");
    await user.selectOptions(within(dialog).getByLabelText("Final attendance"), "late");
    await user.type(within(dialog).getByLabelText("Reason"), "Verified at lecture desk");
    await user.click(within(dialog).getByRole("button", { name: "Save attendance" }));
    await waitFor(() => expect(setStudentAttendance).toHaveBeenCalledWith(
      "session-1", "student-1", { status: "late", reason: "Verified at lecture desk" },
    ));
    await waitFor(() => expect(refresh).toHaveBeenCalledOnce());
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("prefills a manual record and shows a server error without closing", async () => {
    const user = userEvent.setup();
    vi.mocked(setStudentAttendance).mockResolvedValue({
      ok: false, error: "Attendance cannot be changed after cancellation.",
    });
    render(<ManualAttendanceDialog sessionId="session-1" student={{
      ...student, finalStatus: "present", recordSource: "manual",
      manualReason: "Previously confirmed",
    }} />);
    await user.click(screen.getByRole("button", { name: "Change attendance" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByLabelText("Final attendance")).toHaveValue("present");
    expect(within(dialog).getByLabelText("Reason")).toHaveValue("Previously confirmed");
    await user.selectOptions(within(dialog).getByLabelText("Final attendance"), "absent");
    await user.click(within(dialog).getByRole("button", { name: "Save attendance" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("after cancellation");
    expect(refresh).not.toHaveBeenCalled();
  });

  it("requires a reason before calling the server", async () => {
    const user = userEvent.setup();
    render(<ManualAttendanceDialog sessionId="session-1" student={student} />);
    await user.click(screen.getByRole("button", { name: "Set attendance" }));
    const dialog = screen.getByRole("dialog");
    await user.selectOptions(within(dialog).getByLabelText("Final attendance"), "absent");
    await user.type(within(dialog).getByLabelText("Reason"), "x");
    await user.click(within(dialog).getByRole("button", { name: "Save attendance" }));
    expect(within(dialog).getByRole("alert")).toHaveTextContent("3 and 500");
    expect(setStudentAttendance).not.toHaveBeenCalled();
  });
});
