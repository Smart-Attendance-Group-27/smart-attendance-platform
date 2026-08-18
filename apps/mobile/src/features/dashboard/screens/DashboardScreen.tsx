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

import {
  CourseSummaryCard,
  DashboardTopBar,
  UpcomingAttendanceList,
  courseSummaries,
  type CourseSummary,
} from '../../../components/dashboard';
import { ActiveSessionCard } from '../../../components/dashboard/ActiveSessionCard';
import { AppButton, ScreenContainer } from '../../../components/ui';
import { lightColors, spacing, typography } from '../../../theme';
import type { FaceVerificationApiService } from '../../face-verification/services/faceVerificationApiService';
import type { ActiveAttendanceSessionService } from '../services/activeAttendanceSessionService';
import type { DashboardService } from '../services/dashboardService';
import { MockDashboardService } from '../services/mockDashboardService';
import type { Lecture, AttendanceSession } from '../types';
import type { ActiveAttendanceSession } from '../types/activeAttendanceSession';
import type { ProfileService } from '../../profile/services/profile.service';
import { MockProfileService } from '../../profile/services/mockProfileService';
import type { CourseService } from '../../courses/services/courseService';
import type { Course } from '../../courses/mockCoursesData';

type DashboardScreenProps = {
  activeSessionService?: ActiveAttendanceSessionService;
  dashboardService?: DashboardService;
  faceVerificationApiService?: Pick<
    FaceVerificationApiService,
    'getReadinessStatus'
  >;
  courseService?: CourseService;
  onReadinessCheckPress?: () => void;
  profileService?: ProfileService;
  onSignOutPress?: () => void;
};

export function DashboardScreen({
  activeSessionService,
  dashboardService,
  faceVerificationApiService,
  courseService,
  onReadinessCheckPress,
  onSignOutPress,
  profileService,
}: DashboardScreenProps) {
  const router = useRouter();
  const service = useMemo(() => dashboardService ?? new MockDashboardService(), [dashboardService]);
  const profileServiceInstance = useMemo(
    () => profileService ?? new MockProfileService(),
    [profileService],
  );

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lectures, setLectures] = useState<Lecture[]>([]);
  const [activeSessions, setActiveSessions] = useState<AttendanceSession[]>([]);
  const [courseCards, setCourseCards] = useState<CourseSummary[]>([]);
  const [requiresReadinessCheck, setRequiresReadinessCheck] = useState(false);
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

      const content = await loadDashboardContent(
        service,
        activeSessionService,
        faceVerificationApiService,
        courseService,
      );

      setLectures(content.lectures);
      setActiveSessions(content.activeSessions);
      setCourseCards(content.courseCards);
      setRequiresReadinessCheck(content.requiresReadinessCheck);
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
        try {
          const profileResult = await profileServiceInstance.getMyStudentProfile();
          if (profileResult.status === 'found') {
            const full = profileResult.profile.fullName;
            const first = full.split(' ')[0] ?? full;
            setUserName(first);
          }
        } catch {
          // Profile greeting is non-blocking.
        }

        const content = await loadDashboardContent(
          service,
          activeSessionService,
          faceVerificationApiService,
          courseService,
        );

        if (!mounted) return;
        setLectures(content.lectures);
        setActiveSessions(content.activeSessions);
        setCourseCards(content.courseCards);
        setRequiresReadinessCheck(content.requiresReadinessCheck);
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
  }, [activeSessionService, courseService, faceVerificationApiService, profileServiceInstance, service]);

  const handleStart = (sessionId?: string) => {
    if (!sessionId) return;

    router.push({
      pathname: '/(student)/attendance/[sessionId]',
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
            {`Good morning, ${userName || 'student'}`}
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
            {requiresReadinessCheck ? (
              <View style={styles.readinessAction}>
                <AppButton
                  onPress={onReadinessCheckPress}
                  title="Check Face Verification Readiness"
                  variant="secondary"
                />
              </View>
            ) : null}

            {activeSessions.map((activeSession) => (
              <ActiveSessionCard
                key={activeSession.id}
                onStart={() => handleStart(activeSession.id)}
                session={activeSession}
              />
            ))}

            <View style={styles.sectionHeading}>
              <Text style={styles.sectionTitle}>My courses</Text>
              <Pressable
                onPress={() => router.push('/(student)/(tabs)/courses')}
                accessibilityRole="button"
                accessibilityLabel="View all courses"
              >
                <Text style={styles.viewAll}>View all</Text>
              </Pressable>
            </View>

            <ScrollView
              contentContainerStyle={styles.courseRail}
              horizontal
              showsHorizontalScrollIndicator={false}
              style={styles.courseScroll}
            >
              {courseCards.map((course) => (
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

async function loadDashboardContent(
  dashboardService: DashboardService,
  activeSessionService?: ActiveAttendanceSessionService,
  faceVerificationApiService?: Pick<
    FaceVerificationApiService,
    'getReadinessStatus'
  >,
  courseService?: CourseService,
) {
  const [courseData, activeSessions, requiresReadinessCheck] =
    await Promise.all([
      loadCourseDashboardData(dashboardService, courseService),
      loadActiveSessions(dashboardService, activeSessionService),
      loadReadinessRequirement(faceVerificationApiService),
    ]);

  return {
    lectures: courseData.lectures,
    activeSessions,
    courseCards: courseData.courseCards,
    requiresReadinessCheck,
  };
}

async function loadCourseDashboardData(
  dashboardService: DashboardService,
  courseService?: CourseService,
): Promise<{ lectures: Lecture[]; courseCards: CourseSummary[] }> {
  if (!courseService) {
    return {
      lectures: await dashboardService.getUpcomingLectures(),
      courseCards: courseSummaries,
    };
  }

  const result = await courseService.listMyCourses();
  if (result.status !== 'loaded') {
    throw new Error(`Course request failed: ${result.status}`);
  }

  return {
    lectures: result.courses.flatMap(courseToUpcomingLectures),
    courseCards: result.courses.map(courseToSummaryCard),
  };
}

function courseToSummaryCard(course: Course, index: number): CourseSummary {
  const upcomingSessions = course.sessions.filter(
    (session) => session.status === 'upcoming' || session.status === 'active',
  ).length;
  const colors = ['#173B7A', '#1D4ED8', '#254E9A', '#0F4C81', '#1E3A8A'];

  return {
    code: course.code,
    title: course.title,
    lecturer: course.lecturer,
    attendancePercentage: course.attendancePercentage,
    upcomingSessions,
    color: colors[index % colors.length],
  };
}

function courseToUpcomingLectures(course: Course): Lecture[] {
  return course.sessions
    .filter((session) => session.status === 'upcoming')
    .slice(0, 3)
    .map((session) => ({
      id: session.id,
      courseId: course.id,
      courseCode: course.code,
      courseName: course.title,
      startTime: deriveStartTimeFromSession(session.timeText),
      endTime: deriveStartTimeFromSession(session.timeText),
      venue: deriveVenueFromSession(session.timeText),
    }));
}

function deriveStartTimeFromSession(timeText: string): string {
  // The course API already formats session display text for the course detail
  // UI. The dashboard list only needs a stable sort/render value, so use now
  // when the text does not carry a machine date.
  const parts = timeText.split('·').map((part) => part.trim());
  const maybeTime = parts[1]?.split('-')[0]?.trim();
  const today = new Date();
  if (maybeTime && /^\d{2}:\d{2}$/.test(maybeTime)) {
    const [hours, minutes] = maybeTime.split(':').map(Number);
    today.setHours(hours, minutes, 0, 0);
  }
  return today.toISOString();
}

function deriveVenueFromSession(timeText: string): string {
  const parts = timeText.split('·').map((part) => part.trim());
  return parts[2] || 'Venue TBA';
}

async function loadReadinessRequirement(
  service?: Pick<FaceVerificationApiService, 'getReadinessStatus'>,
): Promise<boolean> {
  if (!service) {
    return false;
  }

  const result = await service.getReadinessStatus();
  return (
    result.status === 'loaded' &&
    result.readiness.requiresReadinessCheck
  );
}

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
  readinessAction: {
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
