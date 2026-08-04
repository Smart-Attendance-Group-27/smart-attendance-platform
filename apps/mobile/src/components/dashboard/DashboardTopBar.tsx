import { SymbolView } from 'expo-symbols';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { lightColors, radii, spacing } from '../../theme';

type DashboardTopBarProps = {
  onNotificationsPress: () => void;
};

export function DashboardTopBar({
  onNotificationsPress,
}: DashboardTopBarProps) {
  return (
    <View style={styles.container}>
      <View style={styles.brand}>
        <View style={styles.brandMark}>
          <Text style={styles.brandMarkText}>U</Text>
        </View>
        <Text style={styles.brandTitle}>UniAttend</Text>
      </View>

      <View style={styles.actions}>
        <Pressable
          accessibilityLabel="Open notifications"
          accessibilityRole="button"
          onPress={onNotificationsPress}
          style={({ pressed }) => [
            styles.notificationButton,
            pressed && styles.pressed,
          ]}
        >
          <SymbolView
            name={{ ios: 'bell', android: 'notifications', web: 'notifications' }}
            size={23}
            tintColor={lightColors.textPrimary}
          />
          <View style={styles.notificationDot} />
        </Pressable>

        <View accessibilityLabel="Student profile, Mahesh" style={styles.avatar}>
          <Text style={styles.avatarText}>MH</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    minHeight: 56,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.md,
  },
  brand: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  brandMark: {
    width: 30,
    height: 30,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 9,
    backgroundColor: lightColors.primary,
  },
  brandMarkText: {
    fontSize: 14,
    fontWeight: '800',
    color: lightColors.surface,
  },
  brandTitle: {
    fontSize: 17,
    fontWeight: '700',
    color: lightColors.textPrimary,
  },
  actions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  notificationButton: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.input,
  },
  notificationDot: {
    position: 'absolute',
    top: 7,
    right: 7,
    width: 9,
    height: 9,
    borderWidth: 2,
    borderColor: lightColors.background,
    borderRadius: radii.full,
    backgroundColor: lightColors.accent,
  },
  avatar: {
    width: 36,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1.5,
    borderColor: lightColors.border,
    borderRadius: radii.full,
    backgroundColor: lightColors.primaryLight,
  },
  avatarText: {
    fontSize: 13,
    fontWeight: '700',
    color: lightColors.primary,
  },
  pressed: {
    opacity: 0.65,
  },
});
