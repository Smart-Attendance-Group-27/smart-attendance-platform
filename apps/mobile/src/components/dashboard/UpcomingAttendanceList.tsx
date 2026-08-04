import { SymbolView } from 'expo-symbols';
import { StyleSheet, Text, View } from 'react-native';

import { lightColors, radii, spacing, typography } from '../../theme';
import type { UpcomingAttendance } from './dashboardMockData';

type UpcomingAttendanceListProps = {
  sessions: UpcomingAttendance[];
};

export function UpcomingAttendanceList({
  sessions,
}: UpcomingAttendanceListProps) {
  return (
    <View style={styles.card}>
      {sessions.map((session, index) => (
        <View
          key={session.id}
          style={[styles.row, index === sessions.length - 1 && styles.lastRow]}
        >
          <View style={styles.date}>
            <Text style={styles.day}>{session.day}</Text>
            <Text style={styles.month}>{session.month}</Text>
          </View>
          <View style={styles.copy}>
            <Text style={styles.course}>{session.course}</Text>
            <Text style={styles.details}>
              {session.time} · {session.location}
            </Text>
          </View>
          <View style={styles.upcomingChip}>
            <SymbolView
              name={{
                ios: 'calendar',
                android: 'calendar_month',
                web: 'calendar_month',
              }}
              size={14}
              tintColor={lightColors.neutral}
            />
            <Text style={styles.upcomingText}>Upcoming</Text>
          </View>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    paddingHorizontal: spacing.md,
    borderWidth: 1,
    borderColor: lightColors.border,
    borderRadius: radii.card,
    backgroundColor: lightColors.surface,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    paddingVertical: 13,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: lightColors.border,
  },
  lastRow: {
    borderBottomWidth: 0,
  },
  date: {
    width: 42,
    flexShrink: 0,
    alignItems: 'center',
  },
  day: {
    fontSize: 17,
    fontWeight: '800',
    lineHeight: 19,
    color: lightColors.textPrimary,
  },
  month: {
    fontSize: 10.5,
    fontWeight: '700',
    color: lightColors.textSecondary,
  },
  copy: {
    flex: 1,
    minWidth: 0,
  },
  course: {
    ...typography.cardTitle,
    fontSize: 14.5,
    lineHeight: 20,
    color: lightColors.textPrimary,
  },
  details: {
    ...typography.supporting,
    marginTop: 3,
    color: lightColors.textSecondary,
  },
  upcomingChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xxs,
    paddingHorizontal: spacing.xs,
    paddingVertical: 5,
    borderRadius: radii.full,
    backgroundColor: lightColors.neutralBackground,
  },
  upcomingText: {
    ...typography.caption,
    fontWeight: '700',
    color: lightColors.neutral,
  },
});
