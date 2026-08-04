import { SymbolView, type SymbolViewProps } from 'expo-symbols';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { lightColors, radii, spacing, typography } from '../../theme';
import type {
  NotificationIcon,
  NotificationVariant,
  StudentNotification,
} from './notification.types';

type NotificationItemProps = {
  notification: StudentNotification;
  onPress: (id: string) => void;
};

const iconNames = {
  clock: { ios: 'clock', android: 'schedule', web: 'schedule' },
  'qr-code': { ios: 'qrcode', android: 'qr_code_2', web: 'qr_code_2' },
  'check-circle': {
    ios: 'checkmark.circle',
    android: 'check_circle',
    web: 'check_circle',
  },
  'warning-triangle': {
    ios: 'exclamationmark.triangle',
    android: 'warning',
    web: 'warning',
  },
  'error-circle': {
    ios: 'exclamationmark.circle',
    android: 'error',
    web: 'error',
  },
  location: { ios: 'location', android: 'location_on', web: 'location_on' },
} satisfies Record<NotificationIcon, SymbolViewProps['name']>;

const variantStyles: Record<
  NotificationVariant,
  { backgroundColor: string; color: string }
> = {
  info: {
    backgroundColor: lightColors.infoBackground,
    color: lightColors.info,
  },
  success: {
    backgroundColor: lightColors.successBackground,
    color: lightColors.success,
  },
  warning: {
    backgroundColor: lightColors.warningBackground,
    color: lightColors.warning,
  },
  error: {
    backgroundColor: lightColors.errorBackground,
    color: lightColors.error,
  },
};

export function NotificationItem({
  notification,
  onPress,
}: NotificationItemProps) {
  const variantStyle = variantStyles[notification.variant];

  return (
    <Pressable
      accessibilityHint={
        notification.isRead ? undefined : 'Marks this notification as read'
      }
      accessibilityLabel={`${notification.title}. ${notification.description}. ${notification.timeLabel}${notification.isRead ? '' : '. Unread'}`}
      accessibilityRole="button"
      accessibilityState={{ selected: !notification.isRead }}
      onPress={() => onPress(notification.id)}
      style={({ pressed }) => [styles.row, pressed && styles.pressed]}
    >
      <View
        style={[
          styles.iconContainer,
          { backgroundColor: variantStyle.backgroundColor },
        ]}
      >
        <SymbolView
          name={iconNames[notification.icon]}
          size={22}
          tintColor={variantStyle.color}
        />
      </View>

      <View style={styles.copy}>
        <View style={styles.headingRow}>
          <Text style={styles.title}>{notification.title}</Text>
          <Text style={styles.time}>{notification.timeLabel}</Text>
        </View>
        <Text style={styles.description}>{notification.description}</Text>
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
