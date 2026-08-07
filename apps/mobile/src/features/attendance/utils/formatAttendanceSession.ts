import type {
  AttendanceSession,
  AttendanceSessionType,
} from '../types/attendanceSession';

export type AttendanceDateTimeFormatOptions = {
  locale?: string;
  timeZone?: string;
};

export type FormattedAttendanceSession = {
  date: string;
  scheduledTime: string;
  checkInWindow: string;
  lateThreshold: string;
  sessionType: string;
};

const DEFAULT_LOCALE = 'en-GB';
const DEFAULT_TIME_ZONE = 'Asia/Colombo';

function toValidDate(value: string): Date | null {
  const date = new Date(value);

  return Number.isNaN(date.getTime()) ? null : date;
}

function resolveOptions(
  options: AttendanceDateTimeFormatOptions,
) {
  return {
    locale: options.locale ?? DEFAULT_LOCALE,
    timeZone: options.timeZone ?? DEFAULT_TIME_ZONE,
  };
}

export function formatAttendanceDate(
  value: string,
  options: AttendanceDateTimeFormatOptions = {},
): string {
  const date = toValidDate(value);

  if (!date) {
    return 'Date unavailable';
  }

  const { locale, timeZone } = resolveOptions(options);

  try {
    return new Intl.DateTimeFormat(locale, {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      timeZone,
    }).format(date);
  } catch {
    return 'Date unavailable';
  }
}

export function formatAttendanceTime(
  value: string,
  options: AttendanceDateTimeFormatOptions = {},
): string {
  const date = toValidDate(value);

  if (!date) {
    return 'Time unavailable';
  }

  const { locale, timeZone } = resolveOptions(options);

  try {
    return new Intl.DateTimeFormat(locale, {
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
      timeZone,
    }).format(date);
  } catch {
    return 'Time unavailable';
  }
}

export function formatAttendanceTimeRange(
  startValue: string,
  endValue: string,
  options: AttendanceDateTimeFormatOptions = {},
): string {
  const start = formatAttendanceTime(startValue, options);
  const end = formatAttendanceTime(endValue, options);

  if (start === 'Time unavailable' || end === 'Time unavailable') {
    return 'Time unavailable';
  }

  return `${start}–${end}`;
}

export function formatAttendanceSessionType(
  sessionType: AttendanceSessionType,
): string {
  return sessionType.charAt(0).toUpperCase() + sessionType.slice(1);
}

export function formatAttendanceSession(
  session: AttendanceSession,
  options: AttendanceDateTimeFormatOptions = {},
): FormattedAttendanceSession {
  return {
    date: formatAttendanceDate(session.startTime, options),
    scheduledTime: formatAttendanceTimeRange(
      session.startTime,
      session.endTime,
      options,
    ),
    checkInWindow: formatAttendanceTimeRange(
      session.checkInOpensAt,
      session.checkInClosesAt,
      options,
    ),
    lateThreshold: formatAttendanceTime(
      session.lateThreshold,
      options,
    ),
    sessionType: formatAttendanceSessionType(session.sessionType),
  };
}
