import { describe, expect, it, vi } from "vitest";
import { formatDayOfWeek } from "@/lib/api/format";

vi.mock("server-only", () => ({}));

describe("formatDayOfWeek", () => {
  it("uses the ISO convention written by the admin form: 1 = Monday ... 7 = Sunday", () => {
    expect(
      [1, 2, 3, 4, 5, 6, 7].map(formatDayOfWeek),
    ).toEqual(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]);
  });

  it("falls back to a visible label for out-of-range values", () => {
    expect(formatDayOfWeek(0)).toBe("Day 0");
    expect(formatDayOfWeek(8)).toBe("Day 8");
  });
});
