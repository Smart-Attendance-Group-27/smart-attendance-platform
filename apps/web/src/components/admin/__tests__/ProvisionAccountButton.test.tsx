import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { provisionAccount } from "@/app/actions/users";
import { ProvisionAccountButton } from "@/components/admin/ProvisionAccountButton";

vi.mock("@/app/actions/users", () => ({ provisionAccount: vi.fn() }));
vi.mock("@/components/ui/Dialog", () => ({
  Dialog: ({ open, title, children }: { open: boolean; title: string; children: React.ReactNode }) =>
    open ? <section aria-label={title}>{children}</section> : null,
}));

const departments = [{ id: "department-1", label: "Computer Science" }];

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(provisionAccount).mockResolvedValue({
    ok: true,
    account: {
      userId: "user-1",
      keycloakUserId: "kc-user-1",
      role: "student",
      email: "new.student@example.test",
      temporaryPassword: "Temporary1!Password",
    },
  });
});

describe("ProvisionAccountButton", () => {
  it("switches role-specific fields", () => {
    render(<ProvisionAccountButton departments={departments} />);
    fireEvent.click(screen.getByRole("button", { name: "Provision account" }));

    expect(screen.getByLabelText("Registration number")).toBeInTheDocument();
    expect(screen.queryByLabelText("Employee number")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Lecturer" }));
    expect(screen.getByLabelText("Employee number")).toBeInTheDocument();
    expect(screen.getByLabelText("Designation")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Administrator" }));
    expect(screen.getByLabelText("Administrative scope")).toBeInTheDocument();
  });

  it("submits a student and clears the one-time password when dismissed", async () => {
    render(<ProvisionAccountButton departments={departments} />);
    fireEvent.click(screen.getByRole("button", { name: "Provision account" }));
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "new.student@example.test" } });
    fireEvent.change(screen.getByLabelText("First name"), { target: { value: "New" } });
    fireEvent.change(screen.getByLabelText("Last name"), { target: { value: "Student" } });
    fireEvent.change(screen.getByLabelText("Registration number"), { target: { value: "REG-100" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Provision account" })[1]);

    await waitFor(() => expect(provisionAccount).toHaveBeenCalled());
    expect(screen.getByText("Temporary1!Password")).toBeInTheDocument();
    expect(screen.getByText("Copy this password now")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(screen.queryByText("Temporary1!Password")).not.toBeInTheDocument();
  });
});
