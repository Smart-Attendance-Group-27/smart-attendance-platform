import { describe, expect, it } from "vitest";
import { ADMINISTRATOR_ROLE, dashboardPathForRole, isWebRole, LECTURER_ROLE } from "@/lib/auth/roles";

describe("isWebRole", () => {
  it("accepts the two web roles from the Keycloak realm", () => {
    expect(isWebRole("lecturer")).toBe(true);
    expect(isWebRole("administrator")).toBe(true);
  });

  it("rejects the mobile-only student role and unrelated strings", () => {
    expect(isWebRole("student")).toBe(false);
    expect(isWebRole("admin")).toBe(false);
    expect(isWebRole("")).toBe(false);
  });
});

describe("dashboardPathForRole", () => {
  it("routes administrators to /admin/dashboard", () => {
    expect(dashboardPathForRole(ADMINISTRATOR_ROLE)).toBe("/admin/dashboard");
  });

  it("routes lecturers to /lecturer/dashboard", () => {
    expect(dashboardPathForRole(LECTURER_ROLE)).toBe("/lecturer/dashboard");
  });
});
