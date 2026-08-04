import { useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { ScrollView, StyleSheet, Text, View } from 'react-native';

import {
  ActiveSessionCard,
  CourseSummaryCard,
  DashboardTopBar,
  UpcomingAttendanceList,
  courseSummaries,
  upcomingAttendance,
} from '../../../components/dashboard';
import { ScreenContainer } from '../../../components/ui';
import { lightColors, spacing, typography } from '../../../theme';

export default function StudentHomeScreen() {
  const router = useRouter();

  return (
    <ScreenContainer scrollable contentContainerStyle={styles.screen}>
      <StatusBar style="dark" />
      <DashboardTopBar
        onNotificationsPress={() =>
          router.push('/(student)/(tabs)/notifications')
        }
      />

      <View style={styles.greeting}>
        <Text accessibilityRole="header" style={styles.greetingTitle}>
          Good morning, Mahesh
        </Text>
        <Text style={styles.period}>
          Thursday, 23 July · Semester 1, Year 3
        </Text>
      </View>

      <ActiveSessionCard />

      <View style={styles.sectionHeading}>
        <Text style={styles.sectionTitle}>My courses</Text>
        <Text style={styles.viewAll}>View all</Text>
      </View>
      <ScrollView
        contentContainerStyle={styles.courseRail}
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.courseScroll}
      >
        {courseSummaries.map((course) => (
          <CourseSummaryCard course={course} key={course.code} />
        ))}
      </ScrollView>
      <View style={styles.paginationDots}>
        <View style={styles.activeDot} />
        <View style={styles.dot} />
        <View style={styles.dot} />
        <View style={styles.dot} />
      </View>

      <View style={styles.upcomingHeading}>
        <Text style={styles.sectionTitle}>Upcoming attendance</Text>
      </View>
      <UpcomingAttendanceList sessions={upcomingAttendance} />
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  screen: {
    paddingTop: 6,
    paddingBottom: spacing.xl,
  },
  greeting: {
    marginBottom: spacing.lg,
  },
  greetingTitle: {
    ...typography.screenTitle,
    fontSize: 22,
    lineHeight: 28,
    fontWeight: '800',
    color: lightColors.textPrimary,
  },
  period: {
    ...typography.supporting,
    marginTop: spacing.xxs,
    color: lightColors.textSecondary,
  },
  sectionHeading: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
  },
  sectionTitle: {
    ...typography.sectionTitle,
    color: lightColors.textPrimary,
  },
  viewAll: {
    ...typography.supporting,
    fontWeight: '700',
    color: lightColors.primaryInteraction,
  },
  courseRail: {
    gap: 14,
    paddingRight: spacing.lg,
  },
  courseScroll: {
    minHeight: 164,
  },
  paginationDots: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 6,
    marginTop: 14,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: lightColors.border,
  },
  activeDot: {
    width: spacing.md,
    height: 6,
    borderRadius: 3,
    backgroundColor: lightColors.primaryInteraction,
  },
  upcomingHeading: {
    marginTop: spacing.xl,
    marginBottom: 6,
  },
});
