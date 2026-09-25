import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { UsersWorkspace } from "@/components/admin/UsersWorkspace";
import type { UserDirectoryData } from "@/types/admin";

vi.mock("@/app/actions/users", () => ({ setAccountStatus: vi.fn() }));

const directory: UserDirectoryData = {
  students: [
    {
      userId: "student-1",
      registrationNumber: "OLD001",
      fullName: "Legacy Student",
      email: "legacy.student@example.test",
      department: "Computing",
      intakeYear: 2023,
      currentSemester: 5,
      accountStatus: "inactive",
      profileStatus: "inactive",
    },
  ],
  lecturers: [],
  administrators: [],
};

describe("UsersWorkspace", () => {
  it("renders a legacy inactive account and allows it to be activated", () => {
    render(<UsersWorkspace directory={directory} />);

    expect(screen.getByText("Legacy Student")).toBeInTheDocument();
    expect(screen.getByText("Inactive")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Activate" })).toBeInTheDocument();
  });
});
