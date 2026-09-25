import { describe, expect, jest, test } from '@jest/globals';

import type { CoreApiClient } from '../../../services/api/coreApiClient';
import { CoreApiCourseService } from '../services/coreApiCourseService';

function serviceReturning(data: unknown) {
  const client = { get: jest.fn(async () => ({ status: 'ok' as const, data })) };
  return new CoreApiCourseService(client as unknown as CoreApiClient);
}

const base = {
  id: 'c1',
  code: 'CS3203',
  title: 'Software Engineering Project',
  lecturer: 'Dr N. Perera',
  semester: 'Semester 2, 2026',
  attendedSessions: 0,
  totalSessions: 0,
  attendancePercentage: 0,
  sessions: [],
  attendanceRecords: [],
};

async function firstCourse(data: unknown) {
  const result = await serviceReturning([data]).listMyCourses();
  if (result.status !== 'loaded') throw new Error(`unexpected ${result.status}`);
  return result.courses[0];
}

describe('CoreApiCourseService', () => {
  test('treats a course with no completed sessions as having no percentage', async () => {
    expect((await firstCourse(base)).attendancePercentage).toBeNull();
  });

  test('keeps a real 0% once sessions have been completed', async () => {
    const course = await firstCourse({ ...base, totalSessions: 3, attendancePercentage: 0 });

    expect(course.attendancePercentage).toBe(0);
  });

  test('carries the threshold from the server and tolerates its absence', async () => {
    expect((await firstCourse({ ...base, attendanceThresholdPercent: 75 })).attendanceThresholdPercent).toBe(75);
    expect((await firstCourse(base)).attendanceThresholdPercent).toBeNull();
  });
});
