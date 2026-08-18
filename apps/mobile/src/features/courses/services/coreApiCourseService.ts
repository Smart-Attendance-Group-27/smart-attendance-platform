import type { CoreApiClient } from '../../../services/api/coreApiClient';
import type { Course } from '../mockCoursesData';
import type { CourseService, StudentCoursesResult } from './courseService';

const studentCoursesPath = '/api/v1/students/me/courses';

type StudentCourseResponse = Partial<Record<keyof Course, unknown>>;

export class CoreApiCourseService implements CourseService {
  constructor(private readonly coreApiClient: CoreApiClient) {}

  async listMyCourses(): Promise<StudentCoursesResult> {
    const result = await this.coreApiClient.get<unknown>(studentCoursesPath);

    if (result.status !== 'ok') {
      return { status: result.status };
    }

    if (!Array.isArray(result.data)) {
      return { status: 'server-error' };
    }

    const courses = result.data.map(toCourse);
    if (courses.some((course) => course === null)) {
      return { status: 'server-error' };
    }

    return { status: 'loaded', courses: courses as Course[] };
  }
}

function toCourse(value: unknown): Course | null {
  if (!value || typeof value !== 'object') {
    return null;
  }

  const response = value as StudentCourseResponse;
  if (
    typeof response.id !== 'string' ||
    typeof response.code !== 'string' ||
    typeof response.title !== 'string' ||
    typeof response.lecturer !== 'string' ||
    typeof response.semester !== 'string' ||
    typeof response.attendedSessions !== 'number' ||
    typeof response.totalSessions !== 'number' ||
    typeof response.attendancePercentage !== 'number' ||
    !Array.isArray(response.sessions) ||
    !Array.isArray(response.attendanceRecords)
  ) {
    return null;
  }

  return {
    id: response.id,
    code: response.code,
    title: response.title,
    lecturer: response.lecturer,
    semester: response.semester,
    attendedSessions: response.attendedSessions,
    totalSessions: response.totalSessions,
    attendancePercentage: response.attendancePercentage,
    sessions: response.sessions as Course['sessions'],
    attendanceRecords: response.attendanceRecords as Course['attendanceRecords'],
  };
}
