import { StyleSheet, Text, View } from 'react-native';

import { lightColors, radii, spacing } from '../../theme';
import type { CourseSummary } from './dashboardMockData';

type CourseSummaryCardProps = {
  course: CourseSummary;
};

export function CourseSummaryCard({ course }: CourseSummaryCardProps) {
  return (
    <View style={[styles.card, { backgroundColor: course.color }]}>
      <View style={styles.decorationLarge} />
      <View style={styles.decorationSmall} />
      <Text style={styles.code}>{course.code}</Text>
      <Text style={styles.title}>{course.title}</Text>
      <Text style={styles.lecturer}>{course.lecturer}</Text>
      <View style={styles.meta}>
        <View>
          <Text style={styles.percentage}>{course.attendancePercentage}%</Text>
          <Text style={styles.percentageLabel}>Attendance</Text>
        </View>
        <View style={styles.sessionsChip}>
          <Text style={styles.sessionsText}>
            {course.upcomingSessions} upcoming
          </Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    width: 250,
    minHeight: 164,
    overflow: 'hidden',
    padding: spacing.md,
    borderRadius: radii.card,
  },
  decorationLarge: {
    position: 'absolute',
    top: -65,
    right: -35,
    width: 170,
    height: 170,
    borderRadius: radii.full,
    backgroundColor: 'rgba(255,255,255,0.08)',
  },
  decorationSmall: {
    position: 'absolute',
    right: 35,
    bottom: -35,
    width: 90,
    height: 90,
    borderRadius: radii.full,
    backgroundColor: 'rgba(255,255,255,0.06)',
  },
  code: {
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.4,
    color: 'rgba(255,255,255,0.85)',
  },
  title: {
    marginTop: 6,
    fontSize: 15.5,
    fontWeight: '700',
    lineHeight: 20,
    color: lightColors.surface,
  },
  lecturer: {
    marginTop: 2,
    fontSize: 12,
    color: 'rgba(255,255,255,0.85)',
  },
  meta: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    marginTop: spacing.lg,
  },
  percentage: {
    fontSize: 20,
    fontWeight: '800',
    color: lightColors.surface,
  },
  percentageLabel: {
    fontSize: 10.5,
    color: 'rgba(255,255,255,0.8)',
  },
  sessionsChip: {
    paddingHorizontal: 9,
    paddingVertical: spacing.xxs,
    borderRadius: radii.full,
    backgroundColor: 'rgba(255,255,255,0.18)',
  },
  sessionsText: {
    fontSize: 11.5,
    color: lightColors.surface,
  },
});
