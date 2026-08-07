import { StyleSheet, Text, View } from 'react-native';

import { AppButton, ScreenContainer } from '../../../components/ui';
import { lightColors, radii, spacing, typography } from '../../../theme';

type FaceVerificationScreenProps = {
  sessionId: string;
  onFaceVerified?: (sessionId: string) => void;
};

export function FaceVerificationScreen({
  sessionId,
  onFaceVerified,
}: FaceVerificationScreenProps) {
  return (
    <ScreenContainer>
      <View style={styles.content}>
        <Text accessibilityRole="header" style={styles.title}>
          Face verification
        </Text>
        <Text style={styles.description}>
          The camera and face-verification flow will replace this placeholder.
        </Text>
        <Text style={styles.sessionId}>Session: {sessionId}</Text>

        <View style={styles.mockResultCard}>
          <Text style={styles.mockResultTitle}>
            Mock face verification passed
          </Text>
          <Text style={styles.mockResultText}>
            Continue to scan the lecturer QR code for this testing flow.
          </Text>
        </View>

        <AppButton
          accessibilityLabel="Continue to QR scanner"
          onPress={() => onFaceVerified?.(sessionId)}
          title="Continue to QR Scan"
        />
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: spacing.sm,
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
  mockResultCard: {
    marginTop: spacing.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: lightColors.success,
    borderRadius: radii.card,
    backgroundColor: lightColors.successBackground,
  },
  mockResultTitle: {
    ...typography.cardTitle,
    color: lightColors.success,
  },
  mockResultText: {
    ...typography.body,
    marginTop: spacing.xs,
    color: lightColors.textSecondary,
  },
});
