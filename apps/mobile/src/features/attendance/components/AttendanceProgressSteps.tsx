import { StyleSheet, Text, View } from 'react-native';

import { lightColors, radii, spacing, typography } from '../../../theme';

type AttendanceProgressStepsProps = {
  phase?: 'not_started' | 'location' | 'face';
};

const stepLabels = ['Location', 'Face', 'Complete'] as const;

const stepStatuses = {
  not_started: ['Not started', 'Waiting', 'Not recorded'],
  location: ['Current', 'Waiting', 'Pending'],
  face: ['Verified', 'Current', 'Pending'],
} as const;

export function AttendanceProgressSteps({
  phase = 'not_started',
}: AttendanceProgressStepsProps) {
  const statuses = stepStatuses[phase];

  return (
    <View
      accessible
      accessibilityLabel="Attendance check-in progress: Location, Face, Complete"
      style={styles.container}
    >
      {stepLabels.map((label, index) => {
        const currentStepIndex =
          phase === 'location' ? 0 : phase === 'face' ? 1 : -1;
        const isCurrent = index === currentStepIndex;
        const isVerified = phase === 'face' && index === 0;

        return (
          <View key={label} style={styles.step}>
            {index < stepLabels.length - 1 ? (
              <View
                style={[
                  styles.connector,
                  isVerified && styles.verifiedConnector,
                ]}
              />
            ) : null}
            <View
              style={[
                styles.dot,
                isCurrent && styles.currentDot,
                isVerified && styles.verifiedDot,
              ]}
            >
              <Text
                style={[
                  styles.dotText,
                  isCurrent && styles.currentDotText,
                  isVerified && styles.verifiedDotText,
                ]}
              >
                {isVerified ? '✓' : index + 1}
              </Text>
            </View>
            <Text style={styles.label}>{label}</Text>
            <Text
              style={[
                styles.status,
                isCurrent && styles.currentStatus,
                isVerified && styles.verifiedStatus,
              ]}
            >
              {statuses[index]}
            </Text>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    marginTop: spacing.lg,
  },
  step: {
    position: 'relative',
    flex: 1,
    alignItems: 'center',
  },
  connector: {
    position: 'absolute',
    top: 15,
    left: '50%',
    width: '100%',
    height: 2,
    backgroundColor: lightColors.border,
  },
  verifiedConnector: {
    backgroundColor: lightColors.success,
  },
  dot: {
    width: spacing.xxl,
    height: spacing.xxl,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: lightColors.border,
    borderRadius: radii.full,
    backgroundColor: lightColors.surface,
  },
  dotText: {
    ...typography.caption,
    fontWeight: '700',
    color: lightColors.textSecondary,
  },
  currentDot: {
    borderColor: lightColors.primaryInteraction,
    backgroundColor: lightColors.primaryInteraction,
  },
  currentDotText: {
    color: lightColors.surface,
  },
  verifiedDot: {
    borderColor: lightColors.success,
    backgroundColor: lightColors.success,
  },
  verifiedDotText: {
    color: lightColors.surface,
  },
  label: {
    ...typography.supporting,
    marginTop: spacing.xs,
    fontWeight: '700',
    textAlign: 'center',
    color: lightColors.textPrimary,
  },
  status: {
    ...typography.caption,
    marginTop: spacing.xxs,
    textAlign: 'center',
    color: lightColors.textSecondary,
  },
  currentStatus: {
    fontWeight: '700',
    color: lightColors.primaryInteraction,
  },
  verifiedStatus: {
    fontWeight: '700',
    color: lightColors.success,
  },
});
