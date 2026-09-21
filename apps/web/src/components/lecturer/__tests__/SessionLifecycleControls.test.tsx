import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SessionLifecycleControls } from "@/components/lecturer/SessionLifecycleControls";
import { cancelSession, closeSession } from "@/app/actions/sessions";
import { mockFinalizationSummary } from "@/mocks/fixtures/lecturerLive";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));
vi.mock("@/app/actions/sessions", () => ({
  activateSession: vi.fn(), closeSession: vi.fn(), cancelSession: vi.fn(),
}));

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

describe("SessionLifecycleControls", () => {
  it("confirms close and shows all finalization counts", async () => {
    const user = userEvent.setup();
    vi.mocked(closeSession).mockResolvedValue({ ok: true, finalization: mockFinalizationSummary });
    const view = render(<SessionLifecycleControls sessionId="session-1" status="in_progress" />);

    await user.click(screen.getByRole("button", { name: "Close session" }));
    await user.click(within(screen.getByRole("dialog", { name: "Close session" }))
      .getByRole("button", { name: "Close session" }));

    const summary = await screen.findByRole("dialog", { name: "Session closed" });
    expect(within(summary).getByText("Present")).toBeInTheDocument();
    expect(within(summary).getByText("Manual records kept")).toBeInTheDocument();
    expect(within(summary).getByText("Check-ins reconciled")).toBeInTheDocument();
    expect(within(summary).getByText("QR batches deactivated")).toBeInTheDocument();
    expect(closeSession).toHaveBeenCalledWith("session-1");
    expect(refresh).toHaveBeenCalledOnce();
    view.rerender(<SessionLifecycleControls sessionId="session-1" status="closed" />);
    expect(screen.getByRole("dialog", { name: "Session closed" })).toBeInTheDocument();
  });

  it("explains a null finalization after close", async () => {
    const user = userEvent.setup();
    vi.mocked(closeSession).mockResolvedValue({ ok: true, finalization: null });
    render(<SessionLifecycleControls sessionId="session-1" status="in_progress" />);
    await user.click(screen.getByRole("button", { name: "Close session" }));
    await user.click(within(screen.getByRole("dialog", { name: "Close session" }))
      .getByRole("button", { name: "Close session" }));
    expect(await screen.findByText("The session is closed. Final attendance counts are not available yet."))
      .toBeInTheDocument();
  });

  it("requires a valid reason and submits cancellation", async () => {
    const user = userEvent.setup();
    vi.mocked(cancelSession).mockResolvedValue({ ok: true });
    render(<SessionLifecycleControls sessionId="session-1" status="scheduled" />);
    await user.click(screen.getByRole("button", { name: "Cancel session" }));
    const dialog = screen.getByRole("dialog", { name: "Cancel session" });
    await user.type(within(dialog).getByLabelText("Reason"), "x");
    await user.click(within(dialog).getByRole("button", { name: "Cancel session" }));
    expect(within(dialog).getByRole("alert")).toHaveTextContent("3 and 500");
    expect(cancelSession).not.toHaveBeenCalled();

    await user.clear(within(dialog).getByLabelText("Reason"));
    await user.type(within(dialog).getByLabelText("Reason"), "Lecture moved to another day");
    await user.click(within(dialog).getByRole("button", { name: "Cancel session" }));
    await waitFor(() => expect(cancelSession).toHaveBeenCalledWith(
      "session-1", "Lecture moved to another day",
    ));
    expect(refresh).toHaveBeenCalledOnce();
  });

  it("keeps the cancellation dialog open when the backend rejects it", async () => {
    const user = userEvent.setup();
    vi.mocked(cancelSession).mockResolvedValue({ ok: false, error: "This session is already closed." });
    render(<SessionLifecycleControls sessionId="session-1" status="scheduled" />);
    await user.click(screen.getByRole("button", { name: "Cancel session" }));
    const dialog = screen.getByRole("dialog", { name: "Cancel session" });
    await user.type(within(dialog).getByLabelText("Reason"), "Lecture moved to another day");
    await user.click(within(dialog).getByRole("button", { name: "Cancel session" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("already closed");
    expect(refresh).not.toHaveBeenCalled();
  });

  it("does not offer lifecycle actions for cancelled sessions", () => {
    render(<SessionLifecycleControls sessionId="session-1" status="cancelled" />);
    expect(screen.getByText("Session cancelled")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancel session" })).not.toBeInTheDocument();
  });
});
