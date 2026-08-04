import { StyleSheet, Text, View } from 'react-native';

import { ScreenContainer } from '../../../components/ui';
import { lightColors, spacing, typography } from '../../../theme';

type AttendanceSessionDetailsScreenProps = {
  sessionId: string;
};

export function AttendanceSessionDetailsScreen({
  sessionId,
}: AttendanceSessionDetailsScreenProps) {
  return (
    <ScreenContainer>
      <View style={styles.content}>
        <Text accessibilityRole="header" style={styles.title}>
          Attendance session details
        </Text>
        <Text style={styles.description}>
          The attendance-session details screen will replace this placeholder.
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
