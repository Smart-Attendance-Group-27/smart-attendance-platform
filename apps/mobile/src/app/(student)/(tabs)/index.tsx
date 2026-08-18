import { useMemo } from 'react';
import { useRouter, type Href } from 'expo-router';

import { DashboardScreen } from '../../../features/dashboard/screens/DashboardScreen';
import { useAuth } from '../../../features/auth/context/AuthContext';
import { CoreApiCourseService } from '../../../features/courses/services/coreApiCourseService';
import { CoreApiActiveAttendanceSessionService } from '../../../features/dashboard/services/coreApiActiveAttendanceSessionService';
import { FaceVerificationApiService } from '../../../features/face-verification/services/faceVerificationApiService';
import { CoreApiProfileService } from '../../../features/profile/services/coreApiProfileService';
import { CoreApiClient } from '../../../services/api/coreApiClient';

export default function StudentHomeRoute() {
  const router = useRouter();
  const { session, signOut } = useAuth();
  const accessToken =
    session.status === 'authenticated' ? session.accessToken : undefined;
  const activeSessionService = useMemo(
    () =>
      new CoreApiActiveAttendanceSessionService(
        new CoreApiClient({ getAccessToken: () => accessToken }),
      ),
    [accessToken],
  );
  const courseService = useMemo(
    () =>
      new CoreApiCourseService(
        new CoreApiClient({ getAccessToken: () => accessToken }),
      ),
    [accessToken],
  );
  const profileService = useMemo(
    () =>
      new CoreApiProfileService(
        new CoreApiClient({ getAccessToken: () => accessToken }),
      ),
    [accessToken],
  );
  const faceVerificationApiService = useMemo(
    () =>
      new FaceVerificationApiService({
        getAccessToken: () => accessToken,
      }),
    [accessToken],
  );

  if (session.status !== 'authenticated') {
    return null;
  }

  return (
    <DashboardScreen
      activeSessionService={activeSessionService}
      courseService={courseService}
      faceVerificationApiService={faceVerificationApiService}
      onReadinessCheckPress={() =>
        router.push('/(student)/face-readiness' as Href)
      }
      onSignOutPress={signOut}
      profileService={profileService}
    />
  );
}
