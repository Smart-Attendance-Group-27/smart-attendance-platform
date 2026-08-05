import { SymbolView } from 'expo-symbols';
import { StyleSheet, Text, View } from 'react-native';

import { lightColors, radii, spacing, typography } from '../../../theme';
import type { AttendanceSession } from '../types/attendanceSession';
import type { FormattedAttendanceSession } from '../utils/formatAttendanceSession';

type AttendanceCheckInWindowProps = {
  session: AttendanceSession;
  formattedSession: FormattedAttendanceSession;
};

const statusContent = {
  open: {
    label: 'Open',
    color: lightColors.info,
    backgroundColor: lightColors.infoBackground,
    icon: { ios: 'clock', android: 'schedule', web: 'schedule' },
  },
  not_started: {
    label: 'Scheduled',
    color: lightColors.neutral,
    backgroundColor: lightColors.neutralBackground,
    icon: { ios: 'calendar', android: 'event', web: 'event' },
  },
  closed: {
    label: 'Closed',
    color: lightColors.neutral,
    backgroundColor: lightColors.neutralBackground,
    icon: { ios: 'lock', android: 'lock', web: 'lock' },
  },
} as const;

export function AttendanceCheckInWindow({
  session,
  formattedSession,
}: AttendanceCheckInWindowProps) {
  const status = statusContent[session.checkInStatus];

  return (
    <View
      accessibilityLabel={`Check-in status: ${status.label}`}
      style={[
        styles.container,
        { backgroundColor: status.backgroundColor },
      ]}
    >
      <View style={styles.headingRow}>
        <View style={styles.heading}>
          <SymbolView
            name={{
              ios: 'info.circle',
              android: 'info',
              web: 'info',
            }}
            size={20}
            tintColor={status.color}
          />
          <Text style={[styles.title, { color: status.color }]}>Check-in</Text>
        </View>
        <View style={styles.statusChip}>
          <SymbolView
            name={status.icon}
            size={14}
            tintColor={status.color}
          />
          <Text style={[styles.statusText, { color: status.color }]}>
            {status.label}
          </Text>
        </View>
      </View>

      <Text style={styles.windowText}>
        Check-in window: {formattedSession.checkInWindow}
      </Text>
      <Text style={styles.guidanceText}>
        Arrivals after {formattedSession.lateThreshold} will be marked late.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginTop: spacing.md,
    padding: spacing.sm,
    borderRadius: radii.input,
  },
  headingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.xs,
  },
  heading: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  title: {
    ...typography.cardTitle,
    fontSize: 14,
  },
  statusChip: {
    minHeight: 28,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xxs,
    paddingHorizontal: spacing.xs,
    borderRadius: radii.full,
    backgroundColor: lightColors.surface,
  },
  statusText: {
    ...typography.caption,
    fontWeight: '700',
  },
  windowText: {
    ...typography.body,
    marginTop: spacing.sm,
    fontWeight: '600',
    color: lightColors.textPrimary,
  },
  guidanceText: {
    ...typography.supporting,
    marginTop: spacing.xxs,
    color: lightColors.textSecondary,
  },
});
