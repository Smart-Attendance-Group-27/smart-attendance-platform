import { SymbolView } from 'expo-symbols';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { lightColors, radii, spacing, typography } from '../../../theme';

type NotificationErrorStateProps = {
  onRetry: () => void;
};

export function NotificationErrorState({
  onRetry,
}: NotificationErrorStateProps) {
  return (
    <View accessibilityRole="alert" style={styles.container}>
      <View style={styles.iconContainer}>
        <SymbolView
          name={{ ios: 'wifi.exclamationmark', android: 'wifi_off', web: 'wifi_off' }}
          size={30}
          tintColor={lightColors.error}
        />
      </View>
      <Text style={styles.title}>Notifications could not be loaded</Text>
      <Text style={styles.description}>
        Check your connection and try again.
      </Text>
      <Pressable
        accessibilityLabel="Retry loading notifications"
        accessibilityRole="button"
        onPress={onRetry}
        style={({ pressed }) => [
          styles.retryButton,
          pressed && styles.retryButtonPressed,
        ]}
      >
        <Text style={styles.retryLabel}>Try again</Text>
      </Pressable>
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
    backgroundColor: lightColors.errorBackground,
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
  retryButton: {
    minHeight: 44,
    justifyContent: 'center',
    marginTop: spacing.md,
    paddingHorizontal: spacing.lg,
    borderRadius: radii.full,
    backgroundColor: lightColors.primaryInteraction,
  },
  retryButtonPressed: {
    opacity: 0.75,
  },
  retryLabel: {
    ...typography.button,
    color: lightColors.surface,
  },
});
