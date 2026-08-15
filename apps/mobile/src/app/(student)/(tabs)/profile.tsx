import { useMemo } from 'react';

import { ProfileScreen } from '../../../features/profile/screens/ProfileScreen';
import { CoreApiProfileService } from '../../../features/profile/services/coreApiProfileService';
import { useAuth } from '../../../features/auth/context/AuthContext';
import { CoreApiClient } from '../../../services/api/coreApiClient';

export default function StudentProfileRoute() {
  const { session, signOut } = useAuth();
  const accessToken = session.status === 'authenticated' ? session.accessToken : undefined;

  // Rebuilt when the token changes so a refreshed session is picked up. The
  // token lifecycle stays entirely inside AuthContext; this route only reads it.
  const profileService = useMemo(
    () => new CoreApiProfileService(new CoreApiClient({ getAccessToken: () => accessToken })),
    [accessToken],
  );

  if (session.status !== 'authenticated') {
    return null;
  }

  return (
    <ProfileScreen
      onSignOutPress={signOut}
      profileService={profileService}
      session={session}
    />
  );
}
