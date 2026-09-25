import "server-only";
import { getAppTimeZone } from "@/lib/appTimezone";

const TIME_FORMAT: Intl.DateTimeFormatOptions = { hour: "2-digit", minute: "2-digit", hour12: false };

// academic.timetable_entries.day_of_week is ISO-style: 1 = Monday ... 7 = Sunday.
// This is what the seed data documents and what the admin form and API validation
// (1-7) write, so every reader must use the same convention.
const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export function formatClockTime(isoOrTime: string | null): string {
  if (!isoOrTime) return "—";
  if (/^\d{2}:\d{2}/.test(isoOrTime)) {
    return isoOrTime.slice(0, 5);
  }
  return new Date(isoOrTime).toLocaleTimeString("en-GB", { ...TIME_FORMAT, timeZone: getAppTimeZone() });
}

export function formatTimeRange(startIso: string | null, endIso: string | null): string {
  if (!startIso || !endIso) return "—";
  return `${formatClockTime(startIso)}–${formatClockTime(endIso)}`;
}

export function formatDayOfWeek(dayOfWeek: number): string {
  return DAY_NAMES[dayOfWeek - 1] ?? `Day ${dayOfWeek}`;
}

export function formatDateLabel(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: getAppTimeZone(),
  });
}

export function formatDateTimeLabel(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: getAppTimeZone(),
  });
}

export function roundToOneDecimal(value: number | null): number {
  if (value === null) return 0;
  return Math.round(value * 10) / 10;
}
