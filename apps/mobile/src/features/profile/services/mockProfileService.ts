import type {
  ProfileService,
  StudentProfileResult,
} from './profile.service';
import type { StudentProfile } from '../types/profile.types';

type MockProfileServiceOptions = {
  readonly profilesByUserId?: Readonly<Record<string, StudentProfile>>;
  readonly simulateProfileFailure?: boolean;
};

const defaultProfilesByUserId: Readonly<Record<string, StudentProfile>> = {
  'mock-student-user-1': {
    id: 'mock-student-profile-1',
    registrationNumber: 'UA-0001',
    fullName: 'Avery Mockstudent',
    universityEmail: 'avery.mockstudent@students.uniattend.test',
  },
};

export class MockProfileService implements ProfileService {
  private readonly profilesByUserId: Readonly<Record<string, StudentProfile>>;

  private readonly simulateProfileFailure: boolean;

  constructor({
    profilesByUserId = defaultProfilesByUserId,
    simulateProfileFailure = false,
  }: MockProfileServiceOptions = {}) {
    this.profilesByUserId = profilesByUserId;
    this.simulateProfileFailure = simulateProfileFailure;
  }

  async getStudentProfile(userId: string): Promise<StudentProfileResult> {
    if (this.simulateProfileFailure) {
      return {
        status: 'failed',
      };
    }

    const profile = this.profilesByUserId[userId];

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
