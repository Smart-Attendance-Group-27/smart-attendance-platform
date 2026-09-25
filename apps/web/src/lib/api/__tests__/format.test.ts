import { afterEach, describe, expect, it, vi } from "vitest";
import { formatClockTime, formatDateTimeLabel, formatDayOfWeek } from "@/lib/api/format";

vi.mock("server-only", () => ({}));

afterEach(() => vi.unstubAllEnvs());

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

describe("timestamp formatting", () => {
  it("renders instants in the app timezone regardless of the server timezone", () => {
    vi.stubEnv("APP_TIMEZONE", "Asia/Colombo");
    expect(formatClockTime("2026-09-25T03:30:00Z")).toBe("09:00");
    expect(formatDateTimeLabel("2026-09-25T03:30:00Z")).toContain("09:00");
  });

  it("honours a different configured timezone", () => {
    vi.stubEnv("APP_TIMEZONE", "UTC");
    expect(formatClockTime("2026-09-25T03:30:00Z")).toBe("03:30");
  });

  it("leaves wall-clock timetable times untouched", () => {
    expect(formatClockTime("09:00:00")).toBe("09:00");
  });
});
