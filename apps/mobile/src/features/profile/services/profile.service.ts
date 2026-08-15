import type { StudentProfile } from '../types/profile.types';

/**
 * Outcomes of loading the signed-in student's own profile.
 *
 * Failures are distinct on purpose: the profile screen has to tell a signed-out
 * session apart from a wrong role, a missing profile and an unreachable
 * backend, and must never quietly show mock data instead.
 */
export type StudentProfileResult =
  | {
      readonly status: 'found';
      readonly profile: StudentProfile;
    }
  | {
      readonly status: 'missing';
    }
  | {
      readonly status: 'unauthenticated';
    }
  | {
      readonly status: 'forbidden';
    }
  | {
      readonly status: 'failed';
    };

export type ProfileService = {
  /**
   * Loads the profile of the currently authenticated student. No identifier is
   * passed: the backend derives the student from the access token.
   */
  getMyStudentProfile: () => Promise<StudentProfileResult>;
};
