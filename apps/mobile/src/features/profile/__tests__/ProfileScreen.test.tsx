import { describe, expect, jest, test } from '@jest/globals';
import { fireEvent, render } from '@testing-library/react-native';

import { ProfileScreen } from '../screens/ProfileScreen';
import type { ProfileService } from '../services/profile.service';
import type { StudentProfile } from '../types/profile.types';
import type { AuthenticatedSession } from '../../auth/types/auth.types';

const authenticatedSession: AuthenticatedSession = {
  status: 'authenticated',
  userId: 'student-user-1',
  accessToken: 'access-token',
};

const studentProfile: StudentProfile = {
  id: 'profile-1',
  registrationNumber: 'UA-1001',
  fullName: 'Jordan Sample',
  universityEmail: 'jordan.sample@students.uniattend.test',
};

const noopSignOut = () => undefined;

describe('ProfileScreen', () => {
  test('renders student profile details from the service', async () => {
    const profileService: ProfileService = {
      async getStudentProfile() {
        return {
          status: 'found',
          profile: studentProfile,
        };
      },
    };

    const { findAllByText, findByText } = await render(
      <ProfileScreen
        onSignOutPress={noopSignOut}
        profileService={profileService}
        session={authenticatedSession}
      />,
    );

    expect(await findByText('Jordan Sample')).toBeTruthy();
    expect((await findAllByText('UA-1001')).length).toBeGreaterThan(0);
    expect(await findByText('jordan.sample@students.uniattend.test')).toBeTruthy();
    expect(await findByText('student-user-1')).toBeTruthy();
  });

  test('calls sign out when the account action is pressed', async () => {
    const onSignOutPress = jest.fn(() => undefined);
    const profileService: ProfileService = {
      async getStudentProfile() {
        return {
          status: 'found',
          profile: studentProfile,
        };
      },
    };

    const { findByRole } = await render(
      <ProfileScreen
        onSignOutPress={onSignOutPress}
        profileService={profileService}
        session={authenticatedSession}
      />,
    );

    fireEvent.press(await findByRole('button', { name: 'Sign out of UniAttend' }));

    expect(onSignOutPress).toHaveBeenCalledTimes(1);
  });

  test('shows a missing state when no profile is linked', async () => {
    const profileService: ProfileService = {
      async getStudentProfile() {
        return {
          status: 'missing',
        };
      },
    };

    const { findByText } = await render(
      <ProfileScreen
        onSignOutPress={noopSignOut}
        profileService={profileService}
        session={authenticatedSession}
      />,
    );

    expect(await findByText('Profile not found')).toBeTruthy();
  });

  test('shows a retry action when profile loading fails', async () => {
    const profileService: ProfileService = {
      async getStudentProfile() {
        return {
          status: 'failed',
        };
      },
    };

    const { findByRole, findByText } = await render(
      <ProfileScreen
        onSignOutPress={noopSignOut}
        profileService={profileService}
        session={authenticatedSession}
      />,
    );

    expect(await findByText("We couldn't load your profile")).toBeTruthy();
    expect(await findByRole('button', { name: 'Retry loading profile' })).toBeTruthy();
  });
});
