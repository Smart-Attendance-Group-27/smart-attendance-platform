import { SymbolView, type SymbolViewProps } from 'expo-symbols';
import { StyleSheet, Text, View } from 'react-native';

import { lightColors, radii, spacing, typography } from '../../../theme';
import type { AttendanceSession } from '../types/attendanceSession';
import type { FormattedAttendanceSession } from '../utils/formatAttendanceSession';
import { AttendanceCheckInWindow } from './AttendanceCheckInWindow';

type AttendanceSessionCardProps = {
  session: AttendanceSession;
  formattedSession: FormattedAttendanceSession;
};

type DetailRowProps = {
  icon: SymbolViewProps['name'];
  children: string;
};

function DetailRow({ icon, children }: DetailRowProps) {
  return (
    <View style={styles.detailRow}>
      <SymbolView
        name={icon}
        size={18}
        tintColor={lightColors.textSecondary}
      />
      <Text style={styles.detailText}>{children}</Text>
    </View>
  );
}

export function AttendanceSessionCard({
  session,
  formattedSession,
}: AttendanceSessionCardProps) {
  return (
    <View style={styles.card}>
      <Text style={styles.course}>
        {session.courseCode} · {session.courseName}
      </Text>
      <Text style={styles.sessionTitle}>{session.sessionTitle}</Text>

      <View style={styles.divider} />

      <View style={styles.details}>
        <DetailRow
          icon={{ ios: 'person', android: 'person', web: 'person' }}
        >
          {session.lecturerName}
        </DetailRow>
        <DetailRow
          icon={{
            ios: 'calendar',
            android: 'calendar_month',
            web: 'calendar_month',
          }}
        >
          {formattedSession.date}
        </DetailRow>
        <DetailRow
          icon={{ ios: 'clock', android: 'schedule', web: 'schedule' }}
        >
          {formattedSession.scheduledTime}
        </DetailRow>
        <DetailRow
          icon={{ ios: 'location', android: 'location_on', web: 'location_on' }}
        >
          {session.venue}
        </DetailRow>
        <DetailRow
          icon={{ ios: 'book.closed', android: 'menu_book', web: 'menu_book' }}
        >
          {formattedSession.sessionType}
        </DetailRow>
      </View>

      <AttendanceCheckInWindow
        formattedSession={formattedSession}
        session={session}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    padding: spacing.md,
    borderWidth: 1,
    borderColor: lightColors.border,
    borderRadius: radii.card,
    backgroundColor: lightColors.surface,
    shadowColor: lightColors.primary,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.08,
    shadowRadius: 16,
    elevation: 2,
  },
  course: {
    ...typography.supporting,
    fontWeight: '700',
    color: lightColors.primaryInteraction,
  },
  sessionTitle: {
    ...typography.sectionTitle,
    marginTop: spacing.xxs,
    color: lightColors.textPrimary,
  },
  divider: {
    height: StyleSheet.hairlineWidth,
    marginVertical: spacing.sm,
    backgroundColor: lightColors.border,
  },
  details: {
    gap: spacing.xs,
  },
  detailRow: {
    minHeight: spacing.xl,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  detailText: {
    ...typography.supporting,
    flex: 1,
    color: lightColors.textSecondary,
  },
});
