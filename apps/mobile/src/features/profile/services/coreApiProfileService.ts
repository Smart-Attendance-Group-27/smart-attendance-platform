import type { CoreApiClient } from '../../../services/api/coreApiClient';
import type {
  ProfileService,
  StudentProfileResult,
} from './profile.service';
import type { StudentProfile } from '../types/profile.types';

const studentProfilePath = '/api/v1/students/me/profile';

type StudentProfileResponse = {
  readonly id?: unknown;
  readonly registrationNumber?: unknown;
  readonly fullName?: unknown;
  readonly universityEmail?: unknown;
};

/**
 * Reads the signed-in student's profile from the UniAttend core backend.
 *
 * There is no mock fallback here by design. When the backend cannot answer, the
 * real failure is returned so the screen can show it.
 */
export class CoreApiProfileService implements ProfileService {
  private readonly coreApiClient: CoreApiClient;

  constructor(coreApiClient: CoreApiClient) {
    this.coreApiClient = coreApiClient;
  }

  async getMyStudentProfile(): Promise<StudentProfileResult> {
    const result =
      await this.coreApiClient.get<StudentProfileResponse>(studentProfilePath);

    switch (result.status) {
      case 'ok': {
        const profile = toStudentProfile(result.data);
        return profile ? { status: 'found', profile } : { status: 'failed' };
      }
      case 'unauthenticated':
        return { status: 'unauthenticated' };
      case 'forbidden':
        return { status: 'forbidden' };
      case 'not-found':
        return { status: 'missing' };
      default:
        return { status: 'failed' };
    }
  }
}

function toStudentProfile(
  response: StudentProfileResponse,
): StudentProfile | null {
  if (
    typeof response.id !== 'string' ||
    typeof response.registrationNumber !== 'string' ||
    typeof response.fullName !== 'string' ||
    typeof response.universityEmail !== 'string'
  ) {
    return null;
  }

  return {
    id: response.id,
    registrationNumber: response.registrationNumber,
    fullName: response.fullName,
    universityEmail: response.universityEmail,
  };
}
