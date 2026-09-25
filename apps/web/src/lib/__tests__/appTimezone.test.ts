import { afterEach, describe, expect, it, vi } from "vitest";
import { getAppTimeZone, isSameCalendarDay } from "@/lib/appTimezone";

afterEach(() => vi.unstubAllEnvs());

describe("getAppTimeZone", () => {
  it("defaults to Asia/Colombo", () => {
    vi.stubEnv("APP_TIMEZONE", "");
    expect(getAppTimeZone()).toBe("Asia/Colombo");
  });

  it("uses a valid configured zone and ignores an invalid one", () => {
    vi.stubEnv("APP_TIMEZONE", "Europe/London");
    expect(getAppTimeZone()).toBe("Europe/London");
    vi.stubEnv("APP_TIMEZONE", "Not/AZone");
    expect(getAppTimeZone()).toBe("Asia/Colombo");
  });
});

describe("isSameCalendarDay", () => {
  it("compares days in the app timezone, not the server timezone", () => {
    vi.stubEnv("APP_TIMEZONE", "Asia/Colombo");
    // 20:00 UTC on the 24th is 01:30 on the 25th in Colombo (UTC+5:30).
    const lateEvening = new Date("2026-09-24T20:00:00Z");
    const earlyMorning = new Date("2026-09-25T02:00:00Z");
    expect(isSameCalendarDay(lateEvening, earlyMorning)).toBe(true);
    expect(isSameCalendarDay(new Date("2026-09-24T17:00:00Z"), earlyMorning)).toBe(false);
  });
});
