import { useMemo } from 'react';
import { useRouter } from 'expo-router';

import { useAuth } from '../../features/auth/context/AuthContext';
import { NotificationPreferencesScreen } from '../../features/notifications/screens/NotificationPreferencesScreen';
import { CoreApiNotificationPreferencesService } from '../../features/notifications/services/notificationPreferencesService';
import { CoreApiClient } from '../../services/api/coreApiClient';

export default function NotificationPreferencesRoute() {
  const router = useRouter();
  const { session } = useAuth();
  const token = session.status === 'authenticated' ? session.accessToken : undefined;
  const service = useMemo(
    () => new CoreApiNotificationPreferencesService(
      new CoreApiClient({ getAccessToken: () => token }),
    ),
    [token],
  );
  return <NotificationPreferencesScreen onBack={() => router.back()} service={service} />;
}
