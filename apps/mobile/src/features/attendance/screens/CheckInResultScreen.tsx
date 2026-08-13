import { SymbolView, type SymbolViewProps } from 'expo-symbols';
import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { AppButton, ScreenContainer } from '../../../components/ui';
import {
  lightColors,
  radii,
  spacing,
  typography,
} from '../../../theme';
import { AttendanceProgressSteps } from '../components/AttendanceProgressSteps';
import type { AttendanceService } from '../services/attendanceService';
import type { AttendanceCheckInResult } from '../types/attendanceCheckInResult';
import { formatAttendanceTime } from '../utils/formatAttendanceSession';

type CheckInResultScreenProps = {
  sessionId: string;
  attendanceService: AttendanceService;
  onOpenQrScanner?: () => void;
  onReturnHome: () => void;
};

type CheckInResultScreenState =
  | { status: 'loading' }
  | { status: 'ready'; result: AttendanceCheckInResult }
  | { status: 'unavailable' };

type ResultPresentation = {
  icon: SymbolViewProps['name'];
  label: 'On-time' | 'Late';
  message: string;
  foreground: string;
  background: string;
};

const resultPresentations: Record<
  AttendanceCheckInResult['status'],
  ResultPresentation
> = {
  present: {
    icon: {
      ios: 'checkmark.circle.fill',
      android: 'check_circle',
      web: 'check_circle',
    },
    label: 'On-time',
    message: 'Your attendance has been recorded successfully.',
    foreground: lightColors.success,
    background: lightColors.successBackground,
  },
  late: {
    icon: {
      ios: 'clock.fill',
      android: 'schedule',
      web: 'schedule',
    },
    label: 'Late',
    message: 'Your attendance has been recorded as late.',
    foreground: lightColors.warning,
    background: lightColors.warningBackground,
  },
};

function isSupportedResult(
  sessionId: string,
  result: AttendanceCheckInResult,
) {
  return (
    result.sessionId === sessionId &&
    (result.status === 'present' || result.status === 'late') &&
    result.checkInTime.trim().length > 0
  );
}

export function CheckInResultScreen({
  sessionId,
  attendanceService,
  onOpenQrScanner,
  onReturnHome,
}: CheckInResultScreenProps) {
  const [state, setState] = useState<CheckInResultScreenState>({
    status: 'loading',
  });

  useEffect(() => {
    let isMounted = true;

    attendanceService
      .getCheckInResult(sessionId)
      .then((lookup) => {
        if (!isMounted) {
          return;
        }

        if (
          lookup.status === 'available' &&
          isSupportedResult(sessionId, lookup.result)
        ) {
          setState({ status: 'ready', result: lookup.result });
          return;
        }

        setState({ status: 'unavailable' });
      })
      .catch(() => {
        if (isMounted) {
          setState({ status: 'unavailable' });
        }
      });

    return () => {
      isMounted = false;
    };
  }, [attendanceService, sessionId]);

  if (state.status === 'loading') {
    return (
      <ScreenContainer>
        <View style={styles.stateContent}>
          <ActivityIndicator
            accessible
            accessibilityLabel="Loading check-in result"
            accessibilityRole="progressbar"
            accessibilityState={{ busy: true }}
            color={lightColors.primaryInteraction}
            size="large"
          />
          <Text style={styles.loadingText}>
            Loading your check-in result...
          </Text>
        </View>
      </ScreenContainer>
    );
  }

  if (state.status === 'unavailable') {
    return (
      <ScreenContainer
        scrollable
        contentContainerStyle={styles.screenContent}
      >
        <View style={styles.stateContent}>
          <View style={styles.unavailableIcon}>
            <SymbolView
              name={{
                ios: 'exclamationmark.triangle.fill',
                android: 'warning',
                web: 'warning',
              }}
              size={38}
              tintColor={lightColors.warning}
            />
          </View>
          <Text accessibilityRole="header" style={styles.stateTitle}>
            Check-in result unavailable
          </Text>
          <Text style={styles.stateMessage}>
            We couldn&apos;t load your check-in result.
          </Text>
          <View style={styles.stateAction}>
            <AppButton
              accessibilityLabel="Return to student home"
              onPress={onReturnHome}
              title="Return to Home"
            />
          </View>
        </View>
      </ScreenContainer>
    );
  }

  const presentation = resultPresentations[state.result.status];
  const formattedCheckInTime = formatAttendanceTime(
    state.result.checkInTime,
  );

  return (
    <ScreenContainer
      scrollable
      contentContainerStyle={styles.screenContent}
    >
      <View style={styles.resultContent}>
        <View
          accessible
          accessibilityLabel="Attendance check-in completed successfully"
          style={styles.completionIcon}
        >
          <SymbolView
            name={{
              ios: 'checkmark.circle.fill',
              android: 'check_circle',
              web: 'check_circle',
            }}
            size={54}
            tintColor={lightColors.success}
          />
        </View>

        <Text accessibilityRole="header" style={styles.title}>
          Check-in Confirmed
        </Text>
        <Text style={styles.description}>{presentation.message}</Text>

        <View
          accessible
          accessibilityLabel={`Attendance status: ${presentation.label}. ${presentation.message}`}
          style={[
            styles.statusCard,
            {
              borderColor: presentation.foreground,
              backgroundColor: presentation.background,
            },
          ]}
        >
          <SymbolView
            name={presentation.icon}
            size={28}
            tintColor={presentation.foreground}
          />
          <View style={styles.statusCopy}>
            <Text style={styles.statusCaption}>Check-in Status</Text>
            <Text
              style={[
                styles.statusLabel,
                { color: presentation.foreground },
              ]}
            >
              {presentation.label}
            </Text>
          </View>
        </View>

        <View
          accessible
          accessibilityLabel={`Checked in at ${formattedCheckInTime}`}
          style={styles.timeCard}
        >
          <SymbolView
            name={{ ios: 'clock', android: 'schedule', web: 'schedule' }}
            size={24}
            tintColor={lightColors.primaryInteraction}
          />
          <View style={styles.timeCopy}>
            <Text style={styles.timeCaption}>Checked in at</Text>
            <Text style={styles.timeValue}>{formattedCheckInTime}</Text>
          </View>
        </View>

        <AttendanceProgressSteps phase="complete" />

        <View style={styles.note}>
          <SymbolView
            name={{
              ios: 'checkmark.shield.fill',
              android: 'verified_user',
              web: 'verified_user',
            }}
            size={20}
            tintColor={lightColors.success}
          />
          <Text style={styles.noteText}>
            You&apos;re all checked in for this session.
          </Text>
        </View>

        <View style={styles.action}>
          {onOpenQrScanner ? (
            <AppButton
              accessibilityLabel="Open QR scanner preview"
              onPress={onOpenQrScanner}
              title="Preview QR Scanner"
              variant="secondary"
            />
          ) : null}
          <AppButton
            accessibilityLabel="Return to student home"
            onPress={onReturnHome}
            title="Return to Home"
          />
        </View>
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  screenContent: {
    paddingBottom: spacing.xxl,
  },
  stateContent: {
    flex: 1,
    minHeight: 420,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.sm,
  },
  loadingText: {
    ...typography.body,
    marginTop: spacing.sm,
    textAlign: 'center',
    color: lightColors.textSecondary,
  },
  unavailableIcon: {
    width: 80,
    height: 80,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.full,
    backgroundColor: lightColors.warningBackground,
  },
  stateTitle: {
    ...typography.sectionTitle,
    marginTop: spacing.md,
    textAlign: 'center',
    color: lightColors.textPrimary,
  },
  stateMessage: {
    ...typography.body,
    marginTop: spacing.xs,
    textAlign: 'center',
    color: lightColors.textSecondary,
  },
  stateAction: {
    width: '100%',
    marginTop: spacing.xl,
  },
  resultContent: {
    flex: 1,
  },
  completionIcon: {
    width: 96,
    height: 96,
    alignSelf: 'center',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.full,
    backgroundColor: lightColors.successBackground,
  },
  title: {
    ...typography.screenTitle,
    marginTop: spacing.md,
    textAlign: 'center',
    color: lightColors.textPrimary,
  },
  description: {
    ...typography.body,
    maxWidth: 340,
    alignSelf: 'center',
    marginTop: spacing.xs,
    textAlign: 'center',
    color: lightColors.textSecondary,
  },
  statusCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginTop: spacing.xl,
    padding: spacing.md,
    borderWidth: 1,
    borderRadius: radii.card,
  },
  statusCopy: {
    flex: 1,
  },
  statusCaption: {
    ...typography.supporting,
    color: lightColors.textSecondary,
  },
  statusLabel: {
    ...typography.sectionTitle,
    marginTop: spacing.xxs,
  },
  timeCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginTop: spacing.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: lightColors.border,
    borderRadius: radii.card,
    backgroundColor: lightColors.surface,
  },
  timeCopy: {
    flex: 1,
  },
  timeCaption: {
    ...typography.supporting,
    color: lightColors.textSecondary,
  },
  timeValue: {
    ...typography.sectionTitle,
    marginTop: spacing.xxs,
    color: lightColors.textPrimary,
  },
  note: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.xs,
    marginTop: spacing.lg,
    padding: spacing.sm,
    borderRadius: radii.input,
    backgroundColor: lightColors.successBackground,
  },
  noteText: {
    ...typography.supporting,
    flex: 1,
    color: lightColors.success,
  },
  action: {
    gap: spacing.sm,
    marginTop: spacing.xl,
  },
});
