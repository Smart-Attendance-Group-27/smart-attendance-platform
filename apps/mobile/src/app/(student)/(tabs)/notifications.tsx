import { useMemo } from 'react';

import { useAuth } from '../../../features/auth/context/AuthContext';
import { CoreApiNotificationsService } from '../../../features/notifications/services/coreApiNotificationsService';
import { NotificationsScreen } from '../../../features/notifications/screens/NotificationsScreen';
import { CoreApiClient } from '../../../services/api/coreApiClient';

export default function StudentNotificationsRoute() {
  const { session } = useAuth();
  const accessToken =
    session.status === 'authenticated' ? session.accessToken : undefined;
  const notificationsService = useMemo(
    () =>
      new CoreApiNotificationsService(
        new CoreApiClient({ getAccessToken: () => accessToken }),
      ),
    [accessToken],
  );

  if (session.status !== 'authenticated') {
    return null;
  }

  return <NotificationsScreen notificationsService={notificationsService} />;
}
