import { useMemo } from 'react';

import { DashboardScreen } from '../../../features/dashboard/screens/DashboardScreen';
import { useAuth } from '../../../features/auth/context/AuthContext';
import { CoreApiActiveAttendanceSessionService } from '../../../features/dashboard/services/coreApiActiveAttendanceSessionService';
import { CoreApiClient } from '../../../services/api/coreApiClient';

export default function StudentHomeRoute() {
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

  if (session.status !== 'authenticated') {
    return null;
  }

  return (
    <DashboardScreen
      activeSessionService={activeSessionService}
      onSignOutPress={signOut}
    />
  );
}
