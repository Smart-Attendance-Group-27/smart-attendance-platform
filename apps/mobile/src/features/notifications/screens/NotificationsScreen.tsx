import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ScreenContainer } from '../../../components/ui';
import { lightColors, spacing, typography } from '../../../theme';
import { NotificationEmptyState } from '../components/NotificationEmptyState';
import { NotificationErrorState } from '../components/NotificationErrorState';
import {
  NotificationFilters,
  type NotificationFilter,
} from '../components/NotificationFilters';
import { NotificationItem } from '../components/NotificationItem';
import { NotificationListSkeleton } from '../components/NotificationListSkeleton';
import { MockNotificationsService } from '../services/mockNotificationsService';
import type { NotificationsService } from '../services/notificationsService';
import type { NotificationItem as Notification } from '../types/notification';

type NotificationScreenState = 'loading' | 'loaded' | 'empty' | 'error';

export type NotificationsScreenProps = {
  notificationsService?: NotificationsService;
};

const defaultNotificationsService = new MockNotificationsService();

export function NotificationsScreen({
  notificationsService = defaultNotificationsService,
}: NotificationsScreenProps) {
  const requestId = useRef(0);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [screenState, setScreenState] =
    useState<NotificationScreenState>('loading');
  const [selectedFilter, setSelectedFilter] =
    useState<NotificationFilter>('all');
  const [isUpdating, setIsUpdating] = useState(false);
  const [hasUpdateError, setHasUpdateError] = useState(false);

  const resolveNotificationsRequest = useCallback(async (
    currentRequestId: number,
  ) => {
    try {
      const loadedNotifications =
        await notificationsService.getNotifications();

      if (requestId.current !== currentRequestId) {
        return;
      }

      setNotifications(loadedNotifications);
      setScreenState(loadedNotifications.length > 0 ? 'loaded' : 'empty');
    } catch {
      if (requestId.current === currentRequestId) {
        setNotifications([]);
        setScreenState('error');
      }
    }
  }, [notificationsService]);

  const loadNotifications = useCallback(() => {
    const currentRequestId = requestId.current + 1;
    requestId.current = currentRequestId;
    setScreenState('loading');
    setHasUpdateError(false);
    void resolveNotificationsRequest(currentRequestId);
  }, [resolveNotificationsRequest]);

  useEffect(() => {
    const currentRequestId = requestId.current + 1;
    requestId.current = currentRequestId;
    void resolveNotificationsRequest(currentRequestId);

    return () => {
      requestId.current += 1;
    };
  }, [resolveNotificationsRequest]);

  const filteredNotifications = useMemo(
    () =>
      notifications.filter((notification) => {
        if (selectedFilter === 'all') {
          return true;
        }

        if (selectedFilter === 'general') {
          return notification.type === 'general';
        }

        return notification.type !== 'general';
      }),
    [notifications, selectedFilter],
  );

  const hasUnreadNotifications = notifications.some(
    (notification) => !notification.isRead,
  );

  const markAsRead = useCallback(
    async (notificationId: string) => {
      const notification = notifications.find(
        (item) => item.id === notificationId,
      );

      if (!notification || notification.isRead || isUpdating) {
        return;
      }

      setIsUpdating(true);
      setHasUpdateError(false);

      try {
        await notificationsService.markAsRead(notificationId);
        setNotifications((currentNotifications) =>
          currentNotifications.map((item) =>
            item.id === notificationId ? { ...item, isRead: true } : item,
          ),
        );
      } catch {
        setHasUpdateError(true);
      } finally {
        setIsUpdating(false);
      }
    },
    [isUpdating, notifications, notificationsService],
  );

  const markAllAsRead = useCallback(async () => {
    if (!hasUnreadNotifications || isUpdating) {
      return;
    }

    setIsUpdating(true);
    setHasUpdateError(false);

    try {
      const unreadNotificationIds = notifications
        .filter((notification) => !notification.isRead)
        .map((notification) => notification.id);

      await Promise.all(
        unreadNotificationIds.map((notificationId) =>
          notificationsService.markAsRead(notificationId),
        ),
      );
      setNotifications((currentNotifications) =>
        currentNotifications.map((notification) => ({
          ...notification,
          isRead: true,
        })),
      );
    } catch {
      setHasUpdateError(true);
    } finally {
      setIsUpdating(false);
    }
  }, [
    hasUnreadNotifications,
    isUpdating,
    notifications,
    notificationsService,
  ]);

  return (
    <ScreenContainer scrollable contentContainerStyle={styles.screen}>
      <View style={styles.header}>
        <Text accessibilityRole="header" style={styles.title}>
          Notifications
        </Text>

        {screenState === 'loaded' ? (
          <Pressable
            accessibilityLabel="Mark all notifications as read"
            accessibilityRole="button"
            accessibilityState={{
              busy: isUpdating,
              disabled: !hasUnreadNotifications || isUpdating,
            }}
            disabled={!hasUnreadNotifications || isUpdating}
            onPress={() => void markAllAsRead()}
            style={({ pressed }) => [
              styles.markAllButton,
              pressed && styles.markAllPressed,
            ]}
          >
            <Text
              style={[
                styles.markAllLabel,
                (!hasUnreadNotifications || isUpdating) &&
                  styles.markAllLabelDisabled,
              ]}
            >
              Mark all as read
            </Text>
          </Pressable>
        ) : null}
      </View>

      {hasUpdateError ? (
        <Text accessibilityRole="alert" style={styles.updateError}>
          The notification could not be updated. Please try again.
        </Text>
      ) : null}

      {screenState === 'loading' ? <NotificationListSkeleton /> : null}

      {screenState === 'empty' ? <NotificationEmptyState /> : null}

      {screenState === 'error' ? (
        <NotificationErrorState onRetry={() => void loadNotifications()} />
      ) : null}

      {screenState === 'loaded' ? (
        <>
          <NotificationFilters
            onSelectFilter={setSelectedFilter}
            selectedFilter={selectedFilter}
          />

          {filteredNotifications.length > 0 ? (
            <View>
              {filteredNotifications.map((notification) => (
                <NotificationItem
                  disabled={isUpdating}
                  key={notification.id}
                  notification={notification}
                  onPress={(notificationId) =>
                    void markAsRead(notificationId)
                  }
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
  updateError: {
    ...typography.supporting,
    marginBottom: spacing.sm,
    color: lightColors.error,
  },
});
