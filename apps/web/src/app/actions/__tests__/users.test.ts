import { beforeEach, describe, expect, it, vi } from "vitest";
import { revalidatePath } from "next/cache";
import { provisionAccount as provisionAccountRequest } from "@/lib/api/admin";
import { CoreBackendError } from "@/lib/api/coreBackend";
import { provisionAccount } from "@/app/actions/users";

vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));
vi.mock("server-only", () => ({}));
vi.mock("@/lib/api/coreBackend", () => ({
  CoreBackendError: class CoreBackendError extends Error {
    constructor(message: string, public status: number, public path: string) {
      super(message);
    }
  },
}));
vi.mock("@/lib/api/admin", () => ({
  provisionAccount: vi.fn(),
  updateAccountStatus: vi.fn(),
}));

const payload = {
  role: "student" as const,
  email: "new.student@example.test",
  firstName: "New",
  lastName: "Student",
  departmentId: "department-1",
  registrationNumber: "REG-100",
  intakeYear: 2026,
  currentSemester: 1,
};

const account = {
  userId: "user-1",
  keycloakUserId: "kc-user-1",
  role: "student" as const,
  email: payload.email,
  temporaryPassword: "Temporary1!Password",
};

beforeEach(() => vi.clearAllMocks());

describe("account provisioning action", () => {
  it("returns the one-time password and refreshes admin views", async () => {
    vi.mocked(provisionAccountRequest).mockResolvedValue(account);

    expect(await provisionAccount(payload)).toEqual({ ok: true, account });
    expect(provisionAccountRequest).toHaveBeenCalledWith(payload);
    expect(revalidatePath).toHaveBeenCalledWith("/admin/users");
    expect(revalidatePath).toHaveBeenCalledWith("/admin/dashboard");
  });

  it("preserves actionable API errors", async () => {
    vi.mocked(provisionAccountRequest).mockRejectedValue(
      new CoreBackendError("An account with this email already exists.", 409, "/users"),
    );

    expect(await provisionAccount(payload)).toEqual({
      ok: false,
      message: "An account with this email already exists.",
    });
    expect(revalidatePath).not.toHaveBeenCalled();
  });
});
