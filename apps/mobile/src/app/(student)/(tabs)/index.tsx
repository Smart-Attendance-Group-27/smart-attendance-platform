import { useMemo } from 'react';
import { useRouter, type Href } from 'expo-router';

import { DashboardScreen } from '../../../features/dashboard/screens/DashboardScreen';
import { useAuth } from '../../../features/auth/context/AuthContext';
import { CoreApiActiveAttendanceSessionService } from '../../../features/dashboard/services/coreApiActiveAttendanceSessionService';
import { FaceVerificationApiService } from '../../../features/face-verification/services/faceVerificationApiService';
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
      faceVerificationApiService={faceVerificationApiService}
      onReadinessCheckPress={() =>
        router.push('/(student)/face-readiness' as Href)
      }
      onSignOutPress={signOut}
    />
  );
}
