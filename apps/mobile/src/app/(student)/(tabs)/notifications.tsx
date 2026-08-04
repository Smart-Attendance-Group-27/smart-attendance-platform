import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ScreenContainer } from '../../../components/ui';
import {
  NotificationEmptyState,
  NotificationFilters,
  NotificationItem,
  NotificationListSkeleton,
  notificationMockData,
  type NotificationFilter,
  type StudentNotification,
} from '../../../components/notifications';
import {
  lightColors,
  spacing,
  typography,
} from '../../../theme';

type NotificationScreenState = 'loaded' | 'loading' | 'empty';

// Temporarily change this value to preview the loading and empty designs.
const MOCK_SCREEN_STATE: NotificationScreenState = 'loaded';

export default function NotificationsScreen() {
  const [notifications, setNotifications] = useState<StudentNotification[]>(
    notificationMockData,
  );
  const [selectedFilter, setSelectedFilter] =
    useState<NotificationFilter>('all');

  const filteredNotifications = useMemo(
    () =>
      notifications.filter(
        (notification) =>
          selectedFilter === 'all' || notification.category === selectedFilter,
      ),
    [notifications, selectedFilter],
  );

  const hasUnreadNotifications = notifications.some(
    (notification) => !notification.isRead,
  );

  const markAsRead = (notificationId: string) => {
    setNotifications((currentNotifications) =>
      currentNotifications.map((notification) =>
        notification.id === notificationId
          ? { ...notification, isRead: true }
          : notification,
      ),
    );
  };

  const markAllAsRead = () => {
    setNotifications((currentNotifications) =>
      currentNotifications.map((notification) => ({
        ...notification,
        isRead: true,
      })),
    );
  };

  return (
    <ScreenContainer scrollable contentContainerStyle={styles.screen}>
      <View style={styles.header}>
        <Text accessibilityRole="header" style={styles.title}>
          Notifications
        </Text>

        {MOCK_SCREEN_STATE === 'loaded' ? (
          <Pressable
            accessibilityLabel="Mark all notifications as read"
            accessibilityRole="button"
            accessibilityState={{ disabled: !hasUnreadNotifications }}
            disabled={!hasUnreadNotifications}
            onPress={markAllAsRead}
            style={({ pressed }) => [
              styles.markAllButton,
              pressed && styles.markAllPressed,
            ]}
          >
            <Text
              style={[
                styles.markAllLabel,
                !hasUnreadNotifications && styles.markAllLabelDisabled,
              ]}
            >
              Mark all as read
            </Text>
          </Pressable>
        ) : null}
      </View>

      {MOCK_SCREEN_STATE === 'loading' ? <NotificationListSkeleton /> : null}

      {MOCK_SCREEN_STATE === 'empty' ? <NotificationEmptyState /> : null}

      {MOCK_SCREEN_STATE === 'loaded' ? (
        <>
          <NotificationFilters
            onSelectFilter={setSelectedFilter}
            selectedFilter={selectedFilter}
          />

          {filteredNotifications.length > 0 ? (
            <View>
              {filteredNotifications.map((notification) => (
                <NotificationItem
                  key={notification.id}
                  notification={notification}
                  onPress={markAsRead}
                />
              ))}
            </View>
          ) : (
            <NotificationEmptyState filtered />
          )}
        </>
      ) : null}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  screen: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.xs,
    paddingBottom: spacing.lg,
  },
  header: {
    minHeight: 56,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
    marginBottom: spacing.xs,
  },
  title: {
    ...typography.sectionTitle,
    fontSize: 19,
    color: lightColors.textPrimary,
  },
  markAllButton: {
    minHeight: 44,
    justifyContent: 'center',
  },
  markAllPressed: {
    opacity: 0.65,
  },
  markAllLabel: {
    ...typography.supporting,
    fontWeight: '700',
    color: lightColors.primaryInteraction,
  },
  markAllLabelDisabled: {
    color: lightColors.textSecondary,
  },
});
