import { useCallback, useEffect, useMemo, useState } from 'react';
import { Tabs, usePathname } from 'expo-router';
import { SymbolView } from 'expo-symbols';
import { AppState } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useAuth } from '../../../features/auth/context/AuthContext';
import { CoreApiNotificationsService } from '../../../features/notifications/services/coreApiNotificationsService';
import { subscribeNotificationChanges } from '../../../features/notifications/services/notificationEvents';
import { CoreApiClient } from '../../../services/api/coreApiClient';
import { getTabBarHeight } from '../../../components/navigation/tabBarLayout';
import {
  lightColors,
  typography,
} from '../../../theme';

export default function StudentTabsLayout() {
  const insets = useSafeAreaInsets();
  const pathname = usePathname();
  const { session } = useAuth();
  const [unread, setUnread] = useState<{ userId: string; count: number } | null>(null);
  const userId = session.status === 'authenticated' ? session.userId : undefined;
  const accessToken = session.status === 'authenticated' ? session.accessToken : undefined;
  const unreadCount = unread && unread.userId === userId ? unread.count : 0;
  const notificationsService = useMemo(() => new CoreApiNotificationsService(
    new CoreApiClient({ getAccessToken: () => accessToken }),
  ), [accessToken]);
  const refreshUnreadCount = useCallback(() => {
    if (!accessToken || !userId) return;
    void notificationsService.getUnreadCount()
      .then((count) => setUnread({ userId, count }))
      .catch(() => {});
  }, [accessToken, notificationsService, userId]);

  useEffect(() => {
    refreshUnreadCount();
  }, [pathname, refreshUnreadCount]);

  useEffect(() => {
    const unsubscribe = subscribeNotificationChanges(refreshUnreadCount);
    const appState = AppState.addEventListener('change', (state) => {
      if (state === 'active') refreshUnreadCount();
    });
    return () => { unsubscribe(); appState.remove(); };
  }, [refreshUnreadCount]);

  return (
    <Tabs
      backBehavior="initialRoute"
      initialRouteName="index"
      screenOptions={{
        tabBarItemStyle: {
          paddingVertical: 5,
        },
        headerShown: false,
        tabBarActiveTintColor: lightColors.primaryInteraction,
        tabBarInactiveTintColor: lightColors.textSecondary,
        tabBarHideOnKeyboard: true,
        tabBarLabelStyle: {
          ...typography.caption,
        },
        tabBarStyle: {
          height: getTabBarHeight(insets.bottom),
          backgroundColor: lightColors.surface,
          borderTopColor: lightColors.border,
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          tabBarIcon: ({ color, size }) => (
            <SymbolView
              name={{ ios: 'house', android: 'home', web: 'home' }}
              size={size}
              tintColor={color}
            />
          ),
          title: 'Home',
        }}
      />

      <Tabs.Screen
        name="courses"
        options={{
          tabBarIcon: ({ color, size }) => (
            <SymbolView
              name={{ ios: 'book.closed', android: 'menu_book', web: 'menu_book' }}
              size={size}
              tintColor={color}
            />
          ),
          title: 'Courses',
        }}
      />

      <Tabs.Screen
        name="notifications"
        options={{
          tabBarBadge: unreadCount > 99 ? '99+' : unreadCount || undefined,
          tabBarIcon: ({ color, size }) => (
            <SymbolView
              name={{ ios: 'bell', android: 'notifications', web: 'notifications' }}
              size={size}
              tintColor={color}
            />
          ),
          title: 'Notifications',
        }}
      />

      <Tabs.Screen
        name="profile"
        options={{
          href: null,
        }}
      />
    </Tabs>
  );
}
