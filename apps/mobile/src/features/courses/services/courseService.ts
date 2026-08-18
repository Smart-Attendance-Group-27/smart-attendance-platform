import type { Course } from '../mockCoursesData';

export type StudentCoursesResult =
  | { readonly status: 'loaded'; readonly courses: Course[] }
  | {
      readonly status:
        | 'unauthenticated'
        | 'forbidden'
        | 'not-found'
        | 'invalid-request'
        | 'conflict'
        | 'server-error'
        | 'network-error';
    };

export interface CourseService {
  listMyCourses(): Promise<StudentCoursesResult>;
}
