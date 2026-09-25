import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { AppButton, ScreenContainer } from '../../../components/ui';
import { lightColors, spacing, typography } from '../../../theme';
import { NotificationEmptyState } from '../components/NotificationEmptyState';
import { NotificationErrorState } from '../components/NotificationErrorState';
import {
  NotificationFilters,
  type NotificationFilter,
} from '../components/NotificationFilters';
import { NotificationItem } from '../components/NotificationItem';
import { NotificationListSkeleton } from '../components/NotificationListSkeleton';
import type { NotificationsService } from '../services/notificationsService';
import { notifyNotificationChanges } from '../services/notificationEvents';
import { getPushRegistrationStatus, subscribePushRegistrationStatus } from '../services/pushRegistrationStatus';
import type { NotificationItem as Notification } from '../types/notification';

type NotificationScreenState = 'loading' | 'loaded' | 'empty' | 'error';

export type NotificationsScreenProps = {
  notificationsService: NotificationsService;
  refreshKey?: number;
  onOpenNotification?: (notification: Notification) => void;
  onRetryPush?: () => void;
};

const pageSize = 30;

export function NotificationsScreen({
  notificationsService,
  refreshKey = 0,
  onOpenNotification,
  onRetryPush,
}: NotificationsScreenProps) {
  const pushStatus = useSyncExternalStore(
    subscribePushRegistrationStatus, getPushRegistrationStatus, getPushRegistrationStatus,
  );
  const requestId = useRef(0);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [screenState, setScreenState] =
    useState<NotificationScreenState>('loading');
  const [selectedFilter, setSelectedFilter] =
    useState<NotificationFilter>('all');
  const [isUpdating, setIsUpdating] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [hasUpdateError, setHasUpdateError] = useState(false);

  const resolveNotificationsRequest = useCallback(async (
    currentRequestId: number,
  ) => {
    try {
      const page = await notificationsService.getPage(0, pageSize);

      if (requestId.current !== currentRequestId) {
        return;
      }

      setNotifications(page.items);
      setNextOffset(page.nextOffset);
      setUnreadCount(page.unreadCount);
      setScreenState(page.items.length > 0 ? 'loaded' : 'empty');
    } catch {
      if (requestId.current === currentRequestId) {
        setNotifications([]);
        setNextOffset(null);
        setUnreadCount(0);
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
  }, [resolveNotificationsRequest, refreshKey]);

  const loadMore = useCallback(async () => {
    if (nextOffset === null || isLoadingMore) return;
    const currentRequestId = requestId.current;
    setIsLoadingMore(true);
    setHasUpdateError(false);
    try {
      const page = await notificationsService.getPage(nextOffset, pageSize);
      if (requestId.current !== currentRequestId) return;
      setNotifications((current) => {
        const seen = new Set(current.map((item) => item.id));
        return [...current, ...page.items.filter((item) => !seen.has(item.id))];
      });
      setNextOffset(page.nextOffset);
      setUnreadCount(page.unreadCount);
    } catch {
      setHasUpdateError(true);
    } finally {
      setIsLoadingMore(false);
    }
  }, [isLoadingMore, nextOffset, notificationsService]);

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

  const hasUnreadNotifications = unreadCount > 0;

  const markAsRead = useCallback(
    async (notification: Notification) => {
      if (isUpdating) {
        return;
      }
      if (!notification.isRead) {
        setIsUpdating(true);
        setHasUpdateError(false);
        try {
          await notificationsService.markAsRead(notification.id);
          setNotifications((current) => current.map((item) =>
            item.id === notification.id ? { ...item, isRead: true } : item,
          ));
          setUnreadCount((count) => Math.max(count - 1, 0));
          notifyNotificationChanges();
        } catch {
          setHasUpdateError(true);
        } finally {
          setIsUpdating(false);
        }
      }
      onOpenNotification?.(notification);
    },
    [isUpdating, notificationsService, onOpenNotification],
  );

  const markAllAsRead = useCallback(async () => {
    if (!hasUnreadNotifications || isUpdating) {
      return;
    }

    setIsUpdating(true);
    setHasUpdateError(false);

    try {
      await notificationsService.markAllAsRead();
      setNotifications((currentNotifications) =>
        currentNotifications.map((notification) => ({
          ...notification,
          isRead: true,
        })),
      );
      setUnreadCount(0);
      notifyNotificationChanges();
    } catch {
      setHasUpdateError(true);
    } finally {
      setIsUpdating(false);
    }
  }, [
    hasUnreadNotifications,
    isUpdating,
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

      <View style={styles.pushStatus}>
        <Text style={styles.pushStatusText}>
          {pushStatus === 'registered' ? 'This device is registered for push alerts.' :
            pushStatus === 'permission-denied' ? 'Push alerts are off. Enable notifications in Android settings, then retry.' :
            pushStatus === 'error' ? 'Push alerts could not be set up. In-app notifications still work.' :
            pushStatus === 'checking' ? 'Checking push alerts...' :
            pushStatus === 'not-a-physical-device' ? 'Push alerts require a physical Android phone.' :
            'Push alerts are currently available on Android.'}
        </Text>
        {(pushStatus === 'error' || pushStatus === 'permission-denied') && onRetryPush ? (
          <Pressable accessibilityRole="button" accessibilityLabel="Retry push setup"
            onPress={onRetryPush}>
            <Text style={styles.retryPush}>Retry</Text>
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
                  onPress={() => void markAsRead(notification)}
                />
              ))}
            </View>
          ) : (
            <NotificationEmptyState filtered />
          )}
          {nextOffset !== null ? (
            <View style={styles.loadMore}>
              <AppButton
                accessibilityLabel="Load more notifications"
                disabled={isLoadingMore}
                onPress={() => void loadMore()}
                title={isLoadingMore ? 'Loading...' : 'Load more'}
              />
            </View>
          ) : null}
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
  loadMore: { marginTop: spacing.md },
  pushStatus: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    gap: spacing.sm, marginBottom: spacing.sm,
  },
  pushStatusText: { ...typography.supporting, color: lightColors.textSecondary, flex: 1 },
  retryPush: { ...typography.supporting, color: lightColors.primaryInteraction, fontWeight: '700' },
});
