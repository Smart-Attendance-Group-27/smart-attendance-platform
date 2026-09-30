import { SymbolView, type SymbolViewProps } from 'expo-symbols';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';

import { lightColors, radii, spacing, typography } from '../../../theme';
import {
  STEP_STATE_LABELS,
  type AttendanceStep,
  type StepState,
} from '../utils/attendanceSteps';

type StepAppearance = {
  icon: SymbolViewProps['name'] | null;
  color: string;
  background: string;
};

const APPEARANCE: Record<StepState, StepAppearance> = {
  pending: {
    icon: null,
    color: lightColors.neutral,
    background: lightColors.neutralBackground,
  },
  active: {
    icon: { ios: 'arrow.right', android: 'arrow_forward', web: 'arrow_forward' },
    color: lightColors.primaryInteraction,
    background: lightColors.primaryLight,
  },
  processing: {
    icon: null,
    color: lightColors.info,
    background: lightColors.infoBackground,
  },
  passed: {
    icon: { ios: 'checkmark', android: 'check', web: 'check' },
    color: lightColors.success,
    background: lightColors.successBackground,
  },
  failed: {
    icon: { ios: 'xmark', android: 'close', web: 'close' },
    color: lightColors.error,
    background: lightColors.errorBackground,
  },
  // Deliberately not the pass colour or a checkmark: nothing was verified.
  waived: {
    icon: { ios: 'minus', android: 'remove', web: 'remove' },
    color: lightColors.warning,
    background: lightColors.warningBackground,
  },
  partial: {
    icon: { ios: 'exclamationmark', android: 'priority_high', web: 'priority_high' },
    color: lightColors.warning,
    background: lightColors.warningBackground,
  },
  not_required: {
    icon: { ios: 'minus', android: 'remove', web: 'remove' },
    color: lightColors.neutral,
    background: lightColors.neutralBackground,
  },
};

function StepIndicator({ state, position }: { state: StepState; position: number }) {
  const appearance = APPEARANCE[state];
  return (
    <View
      style={[
        styles.indicator,
        { backgroundColor: appearance.background, borderColor: appearance.color },
      ]}
    >
      {state === 'processing' ? (
        <ActivityIndicator color={appearance.color} size="small" />
      ) : appearance.icon ? (
        <SymbolView name={appearance.icon} size={16} tintColor={appearance.color} />
      ) : (
        <Text style={[styles.indicatorNumber, { color: appearance.color }]}>{position}</Text>
      )}
    </View>
  );
}

export function AttendanceTimeline({ steps }: { steps: readonly AttendanceStep[] }) {
  return (
    <View accessibilityRole="list" style={styles.list}>
      {steps.map((step, index) => {
        const appearance = APPEARANCE[step.state];
        const isLast = index === steps.length - 1;
        const stateLabel = STEP_STATE_LABELS[step.state];
        return (
          <View
            accessible
            accessibilityLabel={`${step.title}. ${stateLabel}. ${step.detail}`}
            key={step.key}
            style={styles.row}
            testID={`attendance-step-${step.key}`}
          >
            <View style={styles.rail}>
              <StepIndicator position={index + 1} state={step.state} />
              {!isLast ? (
                <View
                  style={[
                    styles.connector,
                    step.state === 'passed' && styles.connectorDone,
                  ]}
                />
              ) : null}
            </View>
            <View style={[styles.body, !isLast && styles.bodySpacing]}>
              <View style={styles.titleRow}>
                <Text style={styles.title}>{step.title}</Text>
                <View style={[styles.badge, { backgroundColor: appearance.background }]}>
                  <Text style={[styles.badgeText, { color: appearance.color }]}>{stateLabel}</Text>
                </View>
              </View>
              <Text style={styles.detail}>{step.detail}</Text>
            </View>
          </View>
        );
      })}
    </View>
  );
}

const INDICATOR_SIZE = 32;

const styles = StyleSheet.create({
  list: {
    gap: 0,
  },
  row: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  rail: {
    width: INDICATOR_SIZE,
    alignItems: 'center',
  },
  indicator: {
    width: INDICATOR_SIZE,
    height: INDICATOR_SIZE,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1.5,
    borderRadius: radii.full,
  },
  indicatorNumber: {
    ...typography.caption,
    fontWeight: '700',
  },
  connector: {
    flex: 1,
    width: 2,
    minHeight: spacing.md,
    marginVertical: spacing.xxs,
    borderRadius: radii.full,
    backgroundColor: lightColors.border,
  },
  connectorDone: {
    backgroundColor: lightColors.success,
  },
  body: {
    flex: 1,
    minWidth: 0,
    paddingTop: spacing.xxs,
  },
  bodySpacing: {
    paddingBottom: spacing.md,
  },
  titleRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.xs,
  },
  title: {
    ...typography.cardTitle,
    flexShrink: 1,
    color: lightColors.textPrimary,
  },
  badge: {
    paddingHorizontal: spacing.xs,
    paddingVertical: 2,
    borderRadius: radii.full,
  },
  badgeText: {
    ...typography.caption,
    fontWeight: '700',
  },
  detail: {
    ...typography.supporting,
    marginTop: spacing.xxs,
    color: lightColors.textSecondary,
  },
});
