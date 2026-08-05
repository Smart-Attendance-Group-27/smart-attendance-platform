import { SymbolView, type SymbolViewProps } from 'expo-symbols';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { lightColors, radii, spacing, typography } from '../../../theme';
import type { NotificationItem as Notification } from '../types/notification';

type NotificationItemProps = {
  notification: Notification;
  disabled?: boolean;
  onPress: (id: string) => void;
};

type NotificationPresentation = {
  iconName: SymbolViewProps['name'];
  backgroundColor: string;
  color: string;
};

const notificationPresentations = {
  attendance: {
    iconName: { ios: 'clock', android: 'schedule', web: 'schedule' },
    backgroundColor: lightColors.infoBackground,
    color: lightColors.info,
  },
  qr_session: {
    iconName: { ios: 'qrcode', android: 'qr_code_2', web: 'qr_code_2' },
    backgroundColor: lightColors.infoBackground,
    color: lightColors.info,
  },
  attendance_update: {
    iconName: {
      ios: 'checkmark.circle',
      android: 'check_circle',
      web: 'check_circle',
    },
    backgroundColor: lightColors.successBackground,
    color: lightColors.success,
  },
  general: {
    iconName: {
      ios: 'bell',
      android: 'notifications_none',
      web: 'notifications_none',
    },
    backgroundColor: lightColors.neutralBackground,
    color: lightColors.neutral,
  },
} satisfies Record<Notification['type'], NotificationPresentation>;

function formatCreatedAt(createdAt: string): string {
  const date = new Date(createdAt);

  if (Number.isNaN(date.getTime())) {
    return createdAt;
  }

  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const notificationDay = new Date(
    date.getFullYear(),
    date.getMonth(),
    date.getDate(),
  );
  const dayDifference = Math.floor(
    (today.getTime() - notificationDay.getTime()) / 86_400_000,
  );

  if (dayDifference === 0) {
    return date.toLocaleTimeString([], {
      hour: 'numeric',
      minute: '2-digit',
    });
  }

  if (dayDifference === 1) {
    return 'Yesterday';
  }

  if (dayDifference > 1 && dayDifference < 7) {
    return `${dayDifference} days ago`;
  }

  return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

export function NotificationItem({
  notification,
  disabled = false,
  onPress,
}: NotificationItemProps) {
  const presentation = notificationPresentations[notification.type];
  const timeLabel = formatCreatedAt(notification.createdAt);

  return (
    <Pressable
      accessibilityHint={
        notification.isRead ? undefined : 'Marks this notification as read'
      }
      accessibilityLabel={`${notification.title}. ${notification.message}. ${timeLabel}${notification.isRead ? '' : '. Unread'}`}
      accessibilityRole="button"
      accessibilityState={{
        disabled,
        selected: !notification.isRead,
      }}
      disabled={disabled}
      onPress={() => onPress(notification.id)}
      style={({ pressed }) => [styles.row, pressed && styles.pressed]}
    >
      <View
        style={[
          styles.iconContainer,
          { backgroundColor: presentation.backgroundColor },
        ]}
      >
        <SymbolView
          name={presentation.iconName}
          size={22}
          tintColor={presentation.color}
        />
      </View>

      <View style={styles.copy}>
        <View style={styles.headingRow}>
          <Text style={styles.title}>{notification.title}</Text>
          <Text style={styles.time}>{timeLabel}</Text>
        </View>
        <Text style={styles.description}>{notification.message}</Text>
      </View>

      <View style={styles.indicatorSlot}>
        {!notification.isRead ? <View style={styles.unreadDot} /> : null}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    minHeight: 66,
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    paddingVertical: 13,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: lightColors.border,
  },
  pressed: {
    opacity: 0.7,
  },
  iconContainer: {
    width: 40,
    height: 40,
    flexShrink: 0,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.small + 3,
  },
  copy: {
    flex: 1,
    minWidth: 0,
  },
  headingRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: spacing.xs,
  },
  title: {
    ...typography.cardTitle,
    flex: 1,
    fontSize: 14,
    lineHeight: 19,
    color: lightColors.textPrimary,
  },
  time: {
    ...typography.supporting,
    flexShrink: 0,
    fontSize: 13,
    color: lightColors.textSecondary,
  },
  description: {
    ...typography.supporting,
    marginTop: 3,
    color: lightColors.textSecondary,
  },
  indicatorSlot: {
    width: spacing.xs,
    paddingTop: 6,
  },
  unreadDot: {
    width: spacing.xs,
    height: spacing.xs,
    borderRadius: radii.full,
    backgroundColor: lightColors.primaryInteraction,
  },
});
