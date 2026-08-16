import { describe, expect, it } from "vitest";
import { navItemsForRole, pageTitleForPath } from "@/lib/navigation";

describe("navItemsForRole", () => {
  it("gives lecturers the five course-delivery pages", () => {
    const items = navItemsForRole("lecturer");
    expect(items.map((item) => item.href)).toEqual([
      "/lecturer/dashboard",
      "/lecturer/courses",
      "/lecturer/sessions",
      "/lecturer/review",
      "/lecturer/reports",
    ]);
  });

  it("gives administrators only the Administration page", () => {
    const items = navItemsForRole("administrator");
    expect(items.map((item) => item.href)).toEqual(["/admin/dashboard"]);
  });

  it("never leaks a lecturer route into the administrator nav or vice versa", () => {
    const lecturerHrefs = navItemsForRole("lecturer").map((item) => item.href);
    const adminHrefs = navItemsForRole("administrator").map((item) => item.href);
    expect(lecturerHrefs.some((href) => adminHrefs.includes(href))).toBe(false);
  });
});

describe("pageTitleForPath", () => {
  it("matches the deepest nav item whose href prefixes the path", () => {
    expect(pageTitleForPath("lecturer", "/lecturer/sessions/sess-cs3203-today")).toBe("Sessions");
    expect(pageTitleForPath("lecturer", "/lecturer/review")).toBe("Verification review");
    expect(pageTitleForPath("administrator", "/admin/dashboard")).toBe("Administration");
  });

  it("falls back to Overview for an unmatched path", () => {
    expect(pageTitleForPath("lecturer", "/lecturer/profile")).toBe("Overview");
  });
});
