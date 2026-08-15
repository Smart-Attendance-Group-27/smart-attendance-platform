import { describe, expect, jest, test } from '@jest/globals';
import { fireEvent, render } from '@testing-library/react-native';

import { ProfileScreen } from '../screens/ProfileScreen';
import type {
  ProfileService,
  StudentProfileResult,
} from '../services/profile.service';
import { MockProfileService } from '../services/mockProfileService';
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

function serviceReturning(result: StudentProfileResult): ProfileService {
  return {
    async getMyStudentProfile() {
      return result;
    },
  };
}

function renderProfileScreen(
  profileService: ProfileService,
  onSignOutPress: () => void | Promise<void> = noopSignOut,
) {
  return render(
    <ProfileScreen
      onSignOutPress={onSignOutPress}
      profileService={profileService}
      session={authenticatedSession}
    />,
  );
}

describe('ProfileScreen', () => {
  test('renders student profile details from the service', async () => {
    const { findAllByText, findByText } = await renderProfileScreen(
      serviceReturning({ status: 'found', profile: studentProfile }),
    );

    expect(await findByText('Jordan Sample')).toBeTruthy();
    expect((await findAllByText('UA-1001')).length).toBeGreaterThan(0);
    expect(await findByText('jordan.sample@students.uniattend.test')).toBeTruthy();
    expect(await findByText('student-user-1')).toBeTruthy();
  });

  test('shows a loading indicator before the profile arrives', async () => {
    let resolveProfile: (result: StudentProfileResult) => void = () => undefined;
    const profileService: ProfileService = {
      getMyStudentProfile: () =>
        new Promise<StudentProfileResult>((resolve) => {
          resolveProfile = resolve;
        }),
    };

    const { findByText, getByLabelText } = await renderProfileScreen(profileService);

    expect(getByLabelText('Loading profile')).toBeTruthy();

    resolveProfile({ status: 'found', profile: studentProfile });
    expect(await findByText('Jordan Sample')).toBeTruthy();
  });

  test('asks the service for the signed-in student without an identifier', async () => {
    const getMyStudentProfile = jest.fn(async () => ({
      status: 'found' as const,
      profile: studentProfile,
    }));

    const { findByText } = await renderProfileScreen({ getMyStudentProfile });

    expect(await findByText('Jordan Sample')).toBeTruthy();
    expect(getMyStudentProfile).toHaveBeenCalledTimes(1);
    expect(getMyStudentProfile).toHaveBeenCalledWith();
  });

  test('calls sign out when the account action is pressed', async () => {
    const onSignOutPress = jest.fn(() => undefined);

    const { findByRole } = await renderProfileScreen(
      serviceReturning({ status: 'found', profile: studentProfile }),
      onSignOutPress,
    );

    fireEvent.press(await findByRole('button', { name: 'Sign out of UniAttend' }));

    expect(onSignOutPress).toHaveBeenCalledTimes(1);
  });

  test('shows a missing state when no profile is linked', async () => {
    const { findByText } = await renderProfileScreen(
      serviceReturning({ status: 'missing' }),
    );

    expect(await findByText('Profile not found')).toBeTruthy();
  });

  test('shows a session expired state for an unauthenticated result', async () => {
    const { findByText } = await renderProfileScreen(
      serviceReturning({ status: 'unauthenticated' }),
    );

    expect(await findByText('Session expired')).toBeTruthy();
  });

  test('lets an expired session sign in again', async () => {
    const onSignOutPress = jest.fn(() => undefined);

    const { findByRole } = await renderProfileScreen(
      serviceReturning({ status: 'unauthenticated' }),
      onSignOutPress,
    );

    fireEvent.press(
      await findByRole('button', { name: 'Sign out and sign in again' }),
    );

    expect(onSignOutPress).toHaveBeenCalledTimes(1);
  });

  test('shows a forbidden state for a non-student account', async () => {
    const { findByText } = await renderProfileScreen(
      serviceReturning({ status: 'forbidden' }),
    );

    expect(await findByText('Student access required')).toBeTruthy();
  });

  test('shows a retry action when profile loading fails', async () => {
    const { findByRole, findByText } = await renderProfileScreen(
      serviceReturning({ status: 'failed' }),
    );

    expect(await findByText("We couldn't load your profile")).toBeTruthy();
    expect(await findByRole('button', { name: 'Retry loading profile' })).toBeTruthy();
  });

  test('never falls back to mock data when the API fails', async () => {
    const mockProfile = (await new MockProfileService().getMyStudentProfile()) as {
      profile: StudentProfile;
    };

    const { findByText, queryByText } = await renderProfileScreen(
      serviceReturning({ status: 'failed' }),
    );

    expect(await findByText("We couldn't load your profile")).toBeTruthy();
    expect(queryByText(mockProfile.profile.fullName)).toBeNull();
    expect(queryByText(mockProfile.profile.registrationNumber)).toBeNull();
    expect(queryByText(mockProfile.profile.universityEmail)).toBeNull();
  });

  test('retries the request when retry is pressed', async () => {
    const results: StudentProfileResult[] = [
      { status: 'failed' },
      { status: 'found', profile: studentProfile },
    ];
    const getMyStudentProfile = jest.fn(async () => results.shift()!);

    const { findByRole, findByText } = await renderProfileScreen({
      getMyStudentProfile,
    });

    fireEvent.press(await findByRole('button', { name: 'Retry loading profile' }));

    expect(await findByText('Jordan Sample')).toBeTruthy();
    expect(getMyStudentProfile).toHaveBeenCalledTimes(2);
  });
});
