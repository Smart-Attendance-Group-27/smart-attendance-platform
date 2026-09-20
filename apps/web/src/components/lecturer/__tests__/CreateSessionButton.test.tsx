import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CreateSessionButton } from "@/components/lecturer/CreateSessionButton";
import { createSession } from "@/app/actions/sessions";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));
vi.mock("@/app/actions/sessions", () => ({ createSession: vi.fn() }));

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

describe("CreateSessionButton", () => {
  it("shows mandatory geofence and the optional lecture QR setting", async () => {
    const user = userEvent.setup();
    vi.mocked(createSession).mockResolvedValue({ ok: true, sessionId: "session-1" });
    render(<CreateSessionButton timetableOptions={[{ id: "entry-1", label: "CS101 Monday" }]} />);

    await user.click(screen.getByRole("button", { name: "Create session" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("Geofence check is required for every session.")).toBeInTheDocument();
    expect(within(dialog).queryByRole("checkbox", { name: /geofence/i })).not.toBeInTheDocument();
    expect(within(dialog).getByRole("checkbox", { name: "Enable QR checks during the lecture" })).toBeInTheDocument();

    await user.type(within(dialog).getByLabelText("Session title"), "Week 6 lecture");
    await user.click(within(dialog).getByRole("button", { name: "Create session" }));
    expect(createSession).toHaveBeenCalledWith(expect.objectContaining({
      timetableEntryId: "entry-1",
      requiresQr: false,
    }));
  });
});
