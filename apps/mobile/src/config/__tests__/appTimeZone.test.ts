import { afterEach, describe, expect, test } from '@jest/globals';

import { DEFAULT_APP_TIME_ZONE, getAppTimeZone } from '../appTimeZone';
import { formatAttendanceDateTime, formatAttendanceTime } from '../../features/attendance/utils/formatAttendanceSession';

const original = process.env.EXPO_PUBLIC_APP_TIMEZONE;

afterEach(() => {
  if (original === undefined) delete process.env.EXPO_PUBLIC_APP_TIMEZONE;
  else process.env.EXPO_PUBLIC_APP_TIMEZONE = original;
});

describe('getAppTimeZone', () => {
  test('defaults to Asia/Colombo and ignores an invalid value', () => {
    delete process.env.EXPO_PUBLIC_APP_TIMEZONE;
    expect(getAppTimeZone()).toBe(DEFAULT_APP_TIME_ZONE);
    process.env.EXPO_PUBLIC_APP_TIMEZONE = 'Not/AZone';
    expect(getAppTimeZone()).toBe(DEFAULT_APP_TIME_ZONE);
  });

  test('uses a valid configured zone', () => {
    process.env.EXPO_PUBLIC_APP_TIMEZONE = 'UTC';
    expect(getAppTimeZone()).toBe('UTC');
  });
});

describe('institution-time formatting', () => {
  test('shows session times in the app timezone regardless of the device zone', () => {
    delete process.env.EXPO_PUBLIC_APP_TIMEZONE;
    expect(formatAttendanceTime('2026-09-25T03:30:00Z')).toBe('09:00');
    expect(formatAttendanceDateTime('2026-09-25T03:30:00Z')).toContain('09:00');
  });

  test('follows a configured timezone', () => {
    process.env.EXPO_PUBLIC_APP_TIMEZONE = 'UTC';
    expect(formatAttendanceTime('2026-09-25T03:30:00Z')).toBe('03:30');
  });
});
