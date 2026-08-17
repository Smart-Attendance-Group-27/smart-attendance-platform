import "server-only";

const TIME_FORMAT: Intl.DateTimeFormatOptions = { hour: "2-digit", minute: "2-digit", hour12: false };

// academic.timetable_entries.day_of_week (0-6) is undocumented in the schema.
// The one seed row we can independently verify — CS3203 at day_of_week=1 — is a
// Tuesday lecture (confirmed against the course's known schedule), which only
// fits a Python date.weekday()-style 0=Monday..6=Sunday convention. Treat this
// as an inference from real data, not a confirmed contract.
const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export function formatClockTime(isoOrTime: string | null): string {
  if (!isoOrTime) return "—";
  if (/^\d{2}:\d{2}/.test(isoOrTime)) {
    return isoOrTime.slice(0, 5);
  }
  return new Date(isoOrTime).toLocaleTimeString("en-GB", TIME_FORMAT);
}

export function formatTimeRange(startIso: string | null, endIso: string | null): string {
  if (!startIso || !endIso) return "—";
  return `${formatClockTime(startIso)}–${formatClockTime(endIso)}`;
}

export function formatDayOfWeek(dayOfWeek: number): string {
  return DAY_NAMES[dayOfWeek] ?? `Day ${dayOfWeek}`;
}

export function formatDateLabel(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
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
  });
}

export function roundToOneDecimal(value: number | null): number {
  if (value === null) return 0;
  return Math.round(value * 10) / 10;
}
