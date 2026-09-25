export const DEFAULT_APP_TIMEZONE = "Asia/Colombo";

function isValidTimeZone(timeZone: string): boolean {
  try {
    new Intl.DateTimeFormat("en-GB", { timeZone });
    return true;
  } catch {
    return false;
  }
}

// The web server runs in UTC, so anything it renders for people (session
// times, "today") must name the institution's timezone explicitly.
export function getAppTimeZone(): string {
  const configured = process.env.APP_TIMEZONE?.trim();
  return configured && isValidTimeZone(configured) ? configured : DEFAULT_APP_TIMEZONE;
}

function calendarDay(date: Date): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: getAppTimeZone(),
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

export function isSameCalendarDay(a: Date, b: Date): boolean {
  return calendarDay(a) === calendarDay(b);
}
