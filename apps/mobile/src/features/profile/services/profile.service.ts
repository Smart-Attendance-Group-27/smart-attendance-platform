import type { StudentProfile } from '../types/profile.types';

export type StudentProfileResult =
  | {
      readonly status: 'found';
      readonly profile: StudentProfile;
    }
  | {
      readonly status: 'missing';
    }
  | {
      readonly status: 'failed';
    };

export type ProfileService = {
  getStudentProfile: (userId: string) => Promise<StudentProfileResult>;
};
