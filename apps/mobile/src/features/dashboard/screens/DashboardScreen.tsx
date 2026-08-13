import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'expo-router';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { CourseSummaryCard, DashboardTopBar, UpcomingAttendanceList, courseSummaries } from '../../../components/dashboard';
import { ActiveSessionCard } from '../../../components/dashboard/ActiveSessionCard';
import { ScreenContainer } from '../../../components/ui';
import { lightColors, spacing, typography } from '../../../theme';
import type { ActiveAttendanceSessionService } from '../services/activeAttendanceSessionService';
import type { DashboardService } from '../services/dashboardService';
import { MockDashboardService } from '../services/mockDashboardService';
import type { Lecture, AttendanceSession } from '../types';
import type { ActiveAttendanceSession } from '../types/activeAttendanceSession';
import type { ProfileService } from '../../profile/services/profile.service';
import { MockProfileService } from '../../profile/services/mockProfileService';

type DashboardScreenProps = {
  activeSessionService?: ActiveAttendanceSessionService;
  dashboardService?: DashboardService;
  profileService?: ProfileService;
  onSignOutPress?: () => void;
};

export function DashboardScreen({
  activeSessionService,
  dashboardService,
  onSignOutPress,
  profileService,
}: DashboardScreenProps) {
  const router = useRouter();
  const service = useMemo(() => dashboardService ?? new MockDashboardService(), [dashboardService]);
  const profileServiceInstance = profileService ?? new MockProfileService();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lectures, setLectures] = useState<Lecture[]>([]);
  const [activeSessions, setActiveSessions] = useState<AttendanceSession[]>([]);
  const [userName, setUserName] = useState<string>('');

  const today = useMemo(() => new Date(), []);
  const dateString = useMemo(
    () => new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: '2-digit', month: 'long' }).format(today),
    [today]
  );

  const semesterText = useMemo(() => {
    const month = today.getMonth() + 1;
    const semester = month <= 6 ? 1 : 2;
    const year = today.getFullYear();
    return `Semester ${semester}, ${year}`;
  }, [today]);

  const fetchData = async () => {
    setLoading(true);
    setError(null);

    try {
      // Fetch the signed-in student's display name. The backend derives the
      // student from the access token, so no sign-in call and no user ID
      // lookup happens here: authentication stays inside AuthContext.
      try {
        const profileResult = await profileServiceInstance.getMyStudentProfile();
        if (profileResult.status === 'found') {
          const full = profileResult.profile.fullName;
          const first = full.split(' ')[0] ?? full;
          setUserName(first);
        }
      } catch {
        // ignore profile errors - non-blocking
      }

      const upcoming = await service.getUpcomingLectures();
      const active = await loadActiveSessions(
        service,
        activeSessionService,
      );

      setLectures(upcoming);
      setActiveSessions(active);
    } catch (err: any) {
      setError(err?.message ?? 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let mounted = true;

    (async () => {
      if (!mounted) return;
      setLoading(true);
      setError(null);

      try {
        const upcoming = await service.getUpcomingLectures();
        const active = await loadActiveSessions(
          service,
          activeSessionService,
        );

        if (!mounted) return;
        setLectures(upcoming);
        setActiveSessions(active);
      } catch (err: any) {
        if (!mounted) return;
        setError(err?.message ?? 'Unknown error');
      } finally {
        if (!mounted) return;
        setLoading(false);
      }
    })();

    return () => {
      mounted = false;
    };
  }, [activeSessionService, service]);

  const handleStart = (sessionId?: string) => {
    if (!sessionId) return;

    router.push({
      pathname: '/(student)/attendance/[sessionId]/location-check',
      params: { sessionId },
    });
  };

  const mapLectureToUpcoming = (lecture: Lecture) => {
    const date = new Date(lecture.startTime);
    const day = String(date.getDate()).padStart(2, '0');
    const month = date.toLocaleString('en-US', { month: 'short' }).toUpperCase();

    return {
      id: lecture.id,
      day,
      month,
      course: `${lecture.courseCode} — ${lecture.courseName}`,
      time: new Date(lecture.startTime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      location: lecture.venue,
    };
  };

  return (
    <ScreenContainer scrollable contentContainerStyle={styles.scrollContent}>
        <DashboardTopBar
          onNotificationsPress={() => router.push('/(student)/(tabs)/notifications')}
          onProfilePress={() => router.push('/(student)/(tabs)/profile')}
          onSignOutPress={onSignOutPress}
        />

        <View style={styles.greeting}>
          <Text accessibilityRole="header" style={styles.greetingTitle}>
            {`Good morning, ${userName || 'Ashen'}`}
          </Text>
          <Text style={styles.period}>{`${dateString} · ${semesterText}`}</Text>
        </View>

        {loading ? (
          <ActivityIndicator />
        ) : error ? (
          <View>
            <Text>Dashboard could not be loaded</Text>
            <Pressable onPress={fetchData} accessibilityRole="button" accessibilityLabel="Retry dashboard">
              <Text>Retry</Text>
            </Pressable>
          </View>
        ) : (
          <>
            {activeSessions.map((activeSession) => (
              <ActiveSessionCard
                key={activeSession.id}
                onStart={() => handleStart(activeSession.id)}
                session={activeSession}
              />
            ))}

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

            <View style={styles.upcomingHeading}>
              <Text style={styles.sectionTitle}>Upcoming attendance</Text>
            </View>

            {lectures.length === 0 ? (
              <Text>No upcoming attendance</Text>
            ) : (
              <UpcomingAttendanceList sessions={lectures.map(mapLectureToUpcoming)} />
            )}
          </>
        )}
    </ScreenContainer>
  );
}

export default DashboardScreen;

async function loadActiveSessions(
  dashboardService: DashboardService,
  activeSessionService?: ActiveAttendanceSessionService,
): Promise<AttendanceSession[]> {
  if (!activeSessionService) {
    const session = await dashboardService.getActiveAttendanceSession();
    return session ? [session] : [];
  }

  const result = await activeSessionService.listMyActiveSessions();
  if (result.status !== 'loaded') {
    throw new Error(`Active session request failed: ${result.status}`);
  }

  return result.sessions.map(toDashboardSession);
}

function toDashboardSession(
  session: ActiveAttendanceSession,
): AttendanceSession {
  return {
    id: session.id,
    lectureId: session.id,
    courseCode: session.courseCode,
    courseName: session.courseName,
    startTime: session.scheduledStartAt,
    endTime: session.checkInClosesAt,
    lateThreshold: session.lateAfterAt ?? session.checkInClosesAt,
    checkInStatus: 'open',
    sessionTitle: session.sessionTitle,
    venue: session.venue ?? undefined,
  };
}

const styles = StyleSheet.create({
  screen: {
    paddingTop: 6,
    paddingBottom: spacing.xl,
  },
  scrollContent: {
    paddingTop: spacing.xxl,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xl,
    flexGrow: 1,
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
  upcomingHeading: {
    marginTop: spacing.xl,
    marginBottom: 6,
  },
});
