import { StyleSheet, Text, View } from 'react-native';

import { ScreenContainer } from '../../../components/ui';
import { lightColors, spacing, typography } from '../../../theme';

type FaceIntroductionScreenProps = {
  sessionId: string;
};

export function FaceIntroductionScreen({
  sessionId,
}: FaceIntroductionScreenProps) {
  return (
    <ScreenContainer>
      <View style={styles.content}>
        <Text accessibilityRole="header" style={styles.title}>
          Face verification introduction
        </Text>
        <Text style={styles.description}>
          The face-verification instructions will replace this placeholder.
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
