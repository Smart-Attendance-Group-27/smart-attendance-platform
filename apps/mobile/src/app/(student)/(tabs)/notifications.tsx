import { useCallback, useMemo, useState } from 'react';
import { useFocusEffect, useRouter } from 'expo-router';

import { useAuth } from '../../../features/auth/context/AuthContext';
import { CoreApiNotificationsService } from '../../../features/notifications/services/coreApiNotificationsService';
import { NotificationsScreen } from '../../../features/notifications/screens/NotificationsScreen';
import { subscribeNotificationChanges } from '../../../features/notifications/services/notificationEvents';
import { destinationForNotificationItem } from '../../../features/notifications/services/notificationNavigation';
import { registerForPushNotifications } from '../../../features/notifications/services/pushNotificationService';
import { CoreApiClient } from '../../../services/api/coreApiClient';

export default function StudentNotificationsRoute() {
  const { session } = useAuth();
  const router = useRouter();
  const [refreshKey, setRefreshKey] = useState(0);
  const accessToken =
    session.status === 'authenticated' ? session.accessToken : undefined;
  const notificationsService = useMemo(
    () =>
      new CoreApiNotificationsService(
        new CoreApiClient({ getAccessToken: () => accessToken }),
      ),
    [accessToken],
  );

  useFocusEffect(useCallback(() => {
    setRefreshKey((key) => key + 1);
    return subscribeNotificationChanges(() => setRefreshKey((key) => key + 1));
  }, []));

  if (session.status !== 'authenticated') {
    return null;
  }

  return <NotificationsScreen
    notificationsService={notificationsService}
    refreshKey={refreshKey}
    onRetryPush={() => void registerForPushNotifications(
      new CoreApiClient({ getAccessToken: () => accessToken }),
    )}
    onOpenNotification={(item) => {
      const destination = destinationForNotificationItem(item);
      if (destination !== '/(student)/(tabs)/notifications') router.push(destination);
    }}
  />;
}
