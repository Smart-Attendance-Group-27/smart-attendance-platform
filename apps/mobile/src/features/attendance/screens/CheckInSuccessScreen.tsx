import { StyleSheet, Text, View } from 'react-native';

import { ScreenContainer } from '../../../components/ui';
import { lightColors, spacing, typography } from '../../../theme';

type CheckInSuccessScreenProps = {
  sessionId: string;
};

export function CheckInSuccessScreen({
  sessionId,
}: CheckInSuccessScreenProps) {
  return (
    <ScreenContainer>
      <View style={styles.content}>
        <Text accessibilityRole="header" style={styles.title}>
          Attendance check-in result
        </Text>
        <Text style={styles.description}>
          The present-or-late result screen will replace this placeholder.
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
