import { StyleSheet, Text, View } from 'react-native';

import { lightColors, radii, spacing, typography } from '../../../theme';

const steps = [
  { number: '1', label: 'Location', status: 'Not started' },
  { number: '2', label: 'Face', status: 'Waiting' },
  { number: '3', label: 'Complete', status: 'Not recorded' },
] as const;

export function AttendanceProgressSteps() {
  return (
    <View
      accessible
      accessibilityLabel="Attendance check-in progress: Location, Face, Complete"
      style={styles.container}
    >
      {steps.map((step, index) => (
        <View key={step.label} style={styles.step}>
          {index < steps.length - 1 ? <View style={styles.connector} /> : null}
          <View style={styles.dot}>
            <Text style={styles.dotText}>{step.number}</Text>
          </View>
          <Text style={styles.label}>{step.label}</Text>
          <Text style={styles.status}>{step.status}</Text>
        </View>
      ))}
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
});
