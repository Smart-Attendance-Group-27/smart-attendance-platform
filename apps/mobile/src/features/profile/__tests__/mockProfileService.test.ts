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

    await expect(service.getMyStudentProfile()).resolves.toEqual({
      status: 'found',
      profile: {
        id: 'mock-student-profile-1',
        registrationNumber: '230736R',
        fullName: 'Manushan Hasanka',
        universityEmail: 'manushanh.23@cse.mrt.ac.lk',
      },
    });
  });

  test('returns a supplied student profile', async () => {
    const profile: StudentProfile = {
      id: 'profile-1',
      registrationNumber: 'UA-1001',
      fullName: 'Jordan Sample',
      universityEmail: 'jordan.sample@students.uniattend.test',
      profileImageUrl: 'https://assets.uniattend.test/profiles/jordan.png',
    };
    const service = new MockProfileService({ profile });

    await expect(service.getMyStudentProfile()).resolves.toEqual({
      status: 'found',
      profile,
    });
  });

  test('returns missing when no profile is configured', async () => {
    const service = new MockProfileService({ profile: null });

    await expect(service.getMyStudentProfile()).resolves.toEqual({
      status: 'missing',
    });
  });

  test('simulates profile retrieval failure', async () => {
    const service = new MockProfileService({ result: { status: 'failed' } });

    await expect(service.getMyStudentProfile()).resolves.toEqual({
      status: 'failed',
    });
  });

  test('simulates an expired session', async () => {
    const service = new MockProfileService({
      result: { status: 'unauthenticated' },
    });

    await expect(service.getMyStudentProfile()).resolves.toEqual({
      status: 'unauthenticated',
    });
  });

  test('simulates a non-student account', async () => {
    const service = new MockProfileService({ result: { status: 'forbidden' } });

    await expect(service.getMyStudentProfile()).resolves.toEqual({
      status: 'forbidden',
    });
  });
});
