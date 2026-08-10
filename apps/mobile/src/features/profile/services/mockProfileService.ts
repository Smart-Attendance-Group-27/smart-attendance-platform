import type {
  ProfileService,
  StudentProfileResult,
} from './profile.service';
import type { StudentProfile } from '../types/profile.types';

type MockProfileServiceOptions = {
  readonly profilesByUserId?: Readonly<Record<string, StudentProfile>>;
  readonly fallbackProfile?: StudentProfile | null;
  readonly simulateProfileFailure?: boolean;
};

const defaultStudentProfile: StudentProfile = {
  id: 'mock-student-profile-1',
  registrationNumber: '230736R',
  fullName: 'Manushan Hasanka',
  universityEmail: 'manushanh.23@cse.mrt.ac.lk',
};

const defaultProfilesByUserId: Readonly<Record<string, StudentProfile>> = {
  'mock-student-user-1': defaultStudentProfile,
};

export class MockProfileService implements ProfileService {
  private readonly profilesByUserId: Readonly<Record<string, StudentProfile>>;

  private readonly fallbackProfile: StudentProfile | null;

  private readonly simulateProfileFailure: boolean;

  constructor({
    profilesByUserId = defaultProfilesByUserId,
    fallbackProfile = defaultStudentProfile,
    simulateProfileFailure = false,
  }: MockProfileServiceOptions = {}) {
    this.profilesByUserId = profilesByUserId;
    this.fallbackProfile = fallbackProfile;
    this.simulateProfileFailure = simulateProfileFailure;
  }

  async getStudentProfile(userId: string): Promise<StudentProfileResult> {
    if (this.simulateProfileFailure) {
      return {
        status: 'failed',
      };
    }

    const profile = this.profilesByUserId[userId] ?? this.fallbackProfile;

    if (!profile) {
      return {
        status: 'missing',
      };
    }

    return {
      status: 'found',
      profile,
    };
  }
}
