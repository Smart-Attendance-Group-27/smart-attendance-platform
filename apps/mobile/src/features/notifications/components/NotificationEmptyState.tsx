import { SymbolView } from 'expo-symbols';
import { StyleSheet, Text, View } from 'react-native';

import { lightColors, radii, spacing, typography } from '../../../theme';

type NotificationEmptyStateProps = {
  filtered?: boolean;
};

export function NotificationEmptyState({
  filtered = false,
}: NotificationEmptyStateProps) {
  return (
    <View style={styles.container}>
      <View style={styles.iconContainer}>
        <SymbolView
          name={{
            ios: 'bell',
            android: 'notifications_none',
            web: 'notifications_none',
          }}
          size={30}
          tintColor={lightColors.neutral}
        />
      </View>
      <Text style={styles.title}>
        {filtered ? 'No matching notifications' : 'No notifications yet'}
      </Text>
      <Text style={styles.description}>
        {filtered
          ? 'Notifications in this category will appear here.'
          : 'Attendance reminders and alerts will appear here.'}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    paddingTop: 60,
    textAlign: 'center',
  },
  iconContainer: {
    width: 64,
    height: 64,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md,
    borderRadius: radii.full,
    backgroundColor: lightColors.neutralBackground,
  },
  title: {
    ...typography.cardTitle,
    color: lightColors.textPrimary,
  },
  description: {
    ...typography.supporting,
    maxWidth: 280,
    marginTop: 6,
    textAlign: 'center',
    color: lightColors.textSecondary,
  },
});
