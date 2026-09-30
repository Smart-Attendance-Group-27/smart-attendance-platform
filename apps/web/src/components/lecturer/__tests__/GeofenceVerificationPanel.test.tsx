import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { GeofenceVerificationPanel } from "@/components/lecturer/GeofenceVerificationPanel";
import { waiveSessionGeofence } from "@/app/actions/sessions";
import type { SessionVerificationView } from "@/types/lecturer";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));
vi.mock("@/app/actions/sessions", () => ({ waiveSessionGeofence: vi.fn() }));

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

const health = {
  attempted: 193, passed: 6, failed: 187, failureRatePercent: 96.9,
  warning: true, warningMinimumAttempts: 10, warningFailureRatePercent: 70,
};

const required: SessionVerificationView = { geofence: "required", waiver: null, health };

const waived: SessionVerificationView = {
  geofence: "waived",
  health,
  waiver: {
    performedByName: "Dulani Meedeniya", performedAtLabel: "30 Sep 2026, 09:17",
    reasonLabel: "GPS inaccurate", reasonText: "Indoor hall", affectedStudentCount: 187,
  },
};

describe("GeofenceVerificationPanel", () => {
  it("shows geofence health and warns about a session-wide problem", () => {
    render(<GeofenceVerificationPanel sessionId="session-1" verification={required} canWaive />);

    expect(screen.getByText("193")).toBeTruthy();
    expect(screen.getByText("96.9%")).toBeTruthy();
    expect(screen.getByText("Possible session-wide location verification problem detected.")).toBeTruthy();
  });

  it("offers the waiver even without a warning, but never waives by itself", () => {
    render(<GeofenceVerificationPanel
      sessionId="session-1" verification={{ ...required, health: { ...health, warning: false } }} canWaive
    />);

    expect(screen.queryByText("Possible session-wide location verification problem detected.")).toBeNull();
    expect(screen.getByRole("button", { name: "Waive Geofence Requirement" })).toBeTruthy();
    expect(waiveSessionGeofence).not.toHaveBeenCalled();
  });

  it("hides the waiver button when the session is not active", () => {
    render(<GeofenceVerificationPanel sessionId="session-1" verification={required} canWaive={false} />);

    expect(screen.queryByRole("button", { name: "Waive Geofence Requirement" })).toBeNull();
  });

  it("requires a description when the reason is Other", async () => {
    const user = userEvent.setup();
    render(<GeofenceVerificationPanel sessionId="session-1" verification={required} canWaive />);

    await user.click(screen.getByRole("button", { name: "Waive Geofence Requirement" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(/Existing geofence results will not be modified/)).toBeTruthy();
    await user.selectOptions(within(dialog).getByLabelText("Reason"), "OTHER");
    expect(within(dialog).getByLabelText("Description")).toHaveProperty("required", true);
  });

  it("confirms the waiver with a reason and refreshes the dashboard", async () => {
    const user = userEvent.setup();
    vi.mocked(waiveSessionGeofence).mockResolvedValue({ ok: true, created: true });
    render(<GeofenceVerificationPanel sessionId="session-1" verification={required} canWaive />);

    await user.click(screen.getByRole("button", { name: "Waive Geofence Requirement" }));
    const dialog = screen.getByRole("dialog");
    await user.selectOptions(within(dialog).getByLabelText("Reason"), "GPS_INACCURATE");
    await user.type(within(dialog).getByLabelText("Additional note (optional)"), "Indoor hall");
    await user.click(within(dialog).getByRole("button", { name: "Confirm Waiver" }));

    await waitFor(() => expect(refresh).toHaveBeenCalled());
    expect(waiveSessionGeofence).toHaveBeenCalledWith("session-1", "GPS_INACCURATE", "Indoor hall");
  });

  it("shows who waived the requirement, when and why", () => {
    render(<GeofenceVerificationPanel sessionId="session-1" verification={waived} canWaive />);

    expect(screen.getByText("Requirement waived")).toBeTruthy();
    expect(screen.getByText("Dulani Meedeniya")).toBeTruthy();
    expect(screen.getByText("30 Sep 2026, 09:17")).toBeTruthy();
    expect(screen.getByText("GPS inaccurate", { selector: "dd" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Waive Geofence Requirement" })).toBeNull();
    expect(screen.queryByText("Possible session-wide location verification problem detected.")).toBeNull();
  });
});
