import { StyleSheet, Text, View } from 'react-native';

import { ScreenContainer } from '../../../components/ui';
import { lightColors, spacing, typography } from '../../../theme';

type LocationCheckScreenProps = {
  sessionId: string;
};

export function LocationCheckScreen({
  sessionId,
}: LocationCheckScreenProps) {
  return (
    <ScreenContainer>
      <View style={styles.content}>
        <Text accessibilityRole="header" style={styles.title}>
          Location validation
        </Text>
        <Text style={styles.description}>
          The geofence and location-check screen will replace this placeholder.
        </Text>
        <Text style={styles.sessionId}>Session: {sessionId}</Text>
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: spacing.xs,
  },
  title: {
    ...typography.screenTitle,
    color: lightColors.textPrimary,
  },
  description: {
    ...typography.body,
    color: lightColors.textSecondary,
  },
  sessionId: {
    ...typography.supporting,
    color: lightColors.textSecondary,
  },
});
