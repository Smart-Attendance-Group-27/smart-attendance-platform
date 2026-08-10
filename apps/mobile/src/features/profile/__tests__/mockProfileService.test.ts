import {
  describe,
  expect,
  test,
} from '@jest/globals';

import { MockProfileService } from '../services/mockProfileService';
import type { StudentProfile } from '../types/profile.types';

describe('MockProfileService', () => {
  test('returns the default mock profile for the signed-in student', async () => {
    const service = new MockProfileService();

    await expect(
      service.getStudentProfile('keycloak-student-user'),
    ).resolves.toEqual({
      status: 'found',
      profile: {
        id: 'mock-student-profile-1',
        registrationNumber: '230736R',
        fullName: 'Manushan Hasanka',
        universityEmail: 'manushanh.23@cse.mrt.ac.lk',
      },
    });
  });

  test('returns a valid student profile for a known user id', async () => {
    const profile: StudentProfile = {
      id: 'profile-1',
      registrationNumber: 'UA-1001',
      fullName: 'Jordan Sample',
      universityEmail: 'jordan.sample@students.uniattend.test',
      profileImageUrl: 'https://assets.uniattend.test/profiles/jordan.png',
    };
    const service = new MockProfileService({
      profilesByUserId: {
        'student-user-1': profile,
      },
      fallbackProfile: null,
    });

    await expect(
      service.getStudentProfile('student-user-1'),
    ).resolves.toEqual({
      status: 'found',
      profile,
    });
  });

  test('returns missing when no profile exists for the user id', async () => {
    const service = new MockProfileService({
      profilesByUserId: {},
      fallbackProfile: null,
    });

    await expect(
      service.getStudentProfile('unknown-student-user'),
    ).resolves.toEqual({
      status: 'missing',
    });
  });

  test('simulates profile retrieval failure', async () => {
    const service = new MockProfileService({
      simulateProfileFailure: true,
    });

    await expect(
      service.getStudentProfile('mock-student-user-1'),
    ).resolves.toEqual({
      status: 'failed',
    });
  });
});
