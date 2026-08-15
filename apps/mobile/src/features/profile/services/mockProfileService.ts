import type {
  ProfileService,
  StudentProfileResult,
} from './profile.service';
import type { StudentProfile } from '../types/profile.types';

type MockProfileServiceOptions = {
  readonly profile?: StudentProfile | null;
  readonly result?: StudentProfileResult;
};

const defaultStudentProfile: StudentProfile = {
  id: 'mock-student-profile-1',
  registrationNumber: '230736R',
  fullName: 'Manushan Hasanka',
  universityEmail: 'manushanh.23@cse.mrt.ac.lk',
};

/**
 * In-memory profile service for tests and isolated UI work.
 *
 * It is never used as a fallback for a failed API call: the real service
 * reports real failures so the screen can show them.
 */
export class MockProfileService implements ProfileService {
  private readonly profile: StudentProfile | null;

  private readonly result: StudentProfileResult | null;

  constructor({
    profile = defaultStudentProfile,
    result,
  }: MockProfileServiceOptions = {}) {
    this.profile = profile;
    this.result = result ?? null;
  }

  async getMyStudentProfile(): Promise<StudentProfileResult> {
    if (this.result) {
      return this.result;
    }

    if (!this.profile) {
      return {
        status: 'missing',
      };
    }

    return {
      status: 'found',
      profile: this.profile,
    };
  }
}
