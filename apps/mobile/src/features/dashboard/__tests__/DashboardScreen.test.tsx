import { beforeEach, describe, expect, jest, test } from '@jest/globals';
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';

import { DashboardScreen } from '../screens/DashboardScreen';
import type { ActiveAttendanceSessionService } from '../services/activeAttendanceSessionService';
import type { DashboardService } from '../services/dashboardService';
import type { FaceVerificationApiService } from '../../face-verification/services/faceVerificationApiService';
import type { ProfileService } from '../../profile/services/profile.service';
import { MockQrProgressService } from '../../qr/services/mockQrProgressService';
import { resetMockQrStore } from '../../qr/__fixtures__/mockQrStore';
import { mockCourses } from '../../courses/mockCoursesData';
import { resetMockAttendanceStore } from '../../attendance/__fixtures__/mockAttendanceStore';

const fakeProfileService: ProfileService = {
  async getMyStudentProfile() {
    return { status: 'missing' };
  },
};

const mockPush = jest.fn();
let mockFocusCallback:
  | (() => void | (() => void))
  | undefined;

jest.mock('expo-router', () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const React = require('react');

  return {
    useFocusEffect: (callback: () => void | (() => void)) => {
      mockFocusCallback = callback;
      React.useEffect(callback, [callback]);
    },
    useRouter: () => ({
      push: mockPush,
    }),
  };
});

describe('DashboardScreen', () => {
  beforeEach(() => {
    mockPush.mockClear();
    mockFocusCallback = undefined;
  });

  test('renders upcoming lectures from the service', async () => {
    const fakeService: DashboardService = {
      async getUpcomingLectures() {
        return [
          {
            id: 'l1',
            courseId: 'c1',
            courseCode: 'CS101',
            courseName: 'Intro',
            startTime: '2026-07-23T10:00:00.000Z',
            endTime: '2026-07-23T11:00:00.000Z',
            venue: 'Room A',
          },
        ];
      },
      async getActiveAttendanceSession() {
        return null;
      },
    };

    const { findByText } = await render(<DashboardScreen profileService={fakeProfileService} dashboardService={fakeService} />);

    expect(await findByText(/CS101.*Intro/)).toBeTruthy();
  });

  test('shows the semester from the course data, not a guess from the date', async () => {
    const courseService = {
      async listMyCourses() {
        return {
          status: 'loaded' as const,
          courses: mockCourses.slice(0, 1).map((course) => ({ ...course, semester: 'Semester 2, 2031' })),
        };
      },
    };

    const { findByText } = await render(
      <DashboardScreen
        profileService={fakeProfileService}
        dashboardService={createEmptyDashboardService()}
        courseService={courseService}
      />,
    );

    expect(await findByText(/· Semester 2, 2031$/)).toBeTruthy();
  });

  test('omits the semester when there is no course data to take it from', async () => {
    const { findByText, queryByText } = await render(
      <DashboardScreen profileService={fakeProfileService} dashboardService={createEmptyDashboardService()} />,
    );

    await findByText('No upcoming attendance');
    expect(queryByText(/Semester/)).toBeNull();
  });

  test('shows empty state when no lectures', async () => {
    const fakeService: DashboardService = {
      async getUpcomingLectures() {
        return [];
      },
      async getActiveAttendanceSession() {
        return null;
      },
    };

    const { findByText } = await render(<DashboardScreen profileService={fakeProfileService} dashboardService={fakeService} />);

    expect(await findByText('No upcoming attendance')).toBeTruthy();
  });

  test('shows retry on error', async () => {
    const fakeService: DashboardService = {
      async getUpcomingLectures() {
        throw new Error('boom');
      },
      async getActiveAttendanceSession() {
        return null;
      },
    };

    const { findByText, findByLabelText } = await render(<DashboardScreen profileService={fakeProfileService} dashboardService={fakeService} />);

    expect(await findByText('Dashboard could not be loaded')).toBeTruthy();
    expect(await findByLabelText('Retry dashboard')).toBeTruthy();
  });

  test('navigates to session details when Start is pressed', async () => {
    const fakeService: DashboardService = {
      async getUpcomingLectures() {
        return [];
      },
      async getActiveAttendanceSession() {
        return {
          id: 'attendance-session-1',
          lectureId: 'lecture-1',
          courseCode: 'CS3203',
          courseName: 'Software Engineering Project',
          startTime: '2026-07-20T10:00:00.000Z',
          endTime: '2026-07-20T12:00:00.000Z',
          lateThreshold: '2026-07-20T10:10:00.000Z',
          checkInStatus: 'open',
        };
      },
    };

    const { findByRole } = await render(<DashboardScreen profileService={fakeProfileService} dashboardService={fakeService} />);

    const startButton = await findByRole('button', { name: 'Start attendance' });

    fireEvent.press(startButton);

    expect(mockPush).toHaveBeenCalledWith({
      pathname: '/(student)/attendance/[sessionId]',
      params: { sessionId: 'attendance-session-1' },
    });
  });

  test('renders every active session returned by the Core API service', async () => {
    const getActiveAttendanceSession =
      jest.fn<DashboardService['getActiveAttendanceSession']>();
    getActiveAttendanceSession.mockRejectedValue(
      new Error('The mock active-session path must not be used'),
    );
    const dashboardService: DashboardService = {
      async getUpcomingLectures() {
        return [];
      },
      getActiveAttendanceSession,
    };
    const activeSessionService: ActiveAttendanceSessionService = {
      async listMyActiveSessions() {
        return {
          status: 'loaded',
          sessions: [
            buildActiveSession(
              '40000000-0000-0000-0000-000000000001',
              'Geofence Demo - Near Centre',
            ),
            buildActiveSession(
              '40000000-0000-0000-0000-000000000002',
              'Geofence Demo - Far Centre',
            ),
          ],
        };
      },
    };

    const { findAllByRole, findByText } = await render(
      <DashboardScreen
        profileService={fakeProfileService}
        activeSessionService={activeSessionService}
        dashboardService={dashboardService}
      />,
    );

    expect(await findByText('Geofence Demo - Near Centre')).toBeTruthy();
    expect(await findByText('Geofence Demo - Far Centre')).toBeTruthy();
    const startButtons = await findAllByRole('button', {
      name: 'Start attendance',
    });

    fireEvent.press(startButtons[1]);

    expect(mockPush).toHaveBeenCalledWith({
      pathname: '/(student)/attendance/[sessionId]',
      params: {
        sessionId: '40000000-0000-0000-0000-000000000002',
      },
    });
    expect(getActiveAttendanceSession).not.toHaveBeenCalled();
  });

  test('opens Progress for a checked-in student', async () => {
    const activeSessionService: ActiveAttendanceSessionService = {
      async listMyActiveSessions() {
        return {
          status: 'loaded',
          sessions: [
            {
              ...buildActiveSession(
                '40000000-0000-0000-0000-000000000001',
                'Completed attendance',
              ),
              attemptStatus: 'checked_in' as const,
              initialCheckInStatus: 'checked_in' as const,
              checkedInAt: '2026-08-13T05:35:00Z',
            },
          ],
        };
      },
    };

    const screen = await render(
      <DashboardScreen
        profileService={fakeProfileService}
        activeSessionService={activeSessionService}
        dashboardService={createEmptyDashboardService()}
      />,
    );

    fireEvent.press(
      await screen.findByRole('button', { name: 'View progress' }),
    );

    expect(mockPush).toHaveBeenCalledWith({
      pathname:
        '/(student)/attendance/[sessionId]/progress',
      params: {
        sessionId: '40000000-0000-0000-0000-000000000001',
      },
    });
    expect(
      screen.queryByRole('button', { name: 'Start attendance' }),
    ).toBeNull();
  });

  test('shows the C08 QR badge for a checked-in active session', async () => {
    resetMockAttendanceStore();
    resetMockQrStore();
    const sessionId = 'attendance-session-checked-in';
    const dashboardService: DashboardService = {
      async getUpcomingLectures() { return []; },
      async getActiveAttendanceSession() {
        return {
          id: sessionId, lectureId: sessionId, courseCode: 'CS3203',
          courseName: 'Software Engineering Project',
          startTime: '2026-07-20T10:00:00Z', endTime: '2026-07-20T12:00:00Z',
          lateThreshold: '2026-07-20T10:10:00Z', checkInStatus: 'completed' as const,
          initialCheckInStatus: 'checked_in' as const,
        };
      },
    };
    const screen = await render(<DashboardScreen
        profileService={fakeProfileService}
      dashboardService={dashboardService}
      qrProgressService={new MockQrProgressService()}
    />);
    expect(await screen.findByText('QR check active — scan now')).toBeTruthy();
    expect(screen.getByText('QR: 0/2 required batches passed')).toBeTruthy();
  });

  test('refreshes a completed check-in when the dashboard regains focus', async () => {
    const listMyActiveSessions =
      jest.fn<ActiveAttendanceSessionService['listMyActiveSessions']>();
    listMyActiveSessions
      .mockResolvedValueOnce({
        status: 'loaded',
        sessions: [
          buildActiveSession(
            '40000000-0000-0000-0000-000000000001',
            'Attendance in progress',
          ),
        ],
      })
      .mockResolvedValueOnce({
        status: 'loaded',
        sessions: [
          {
            ...buildActiveSession(
              '40000000-0000-0000-0000-000000000001',
              'Attendance in progress',
            ),
            attemptStatus: 'checked_in' as const,
            initialCheckInStatus: 'checked_in' as const,
            checkedInAt: '2026-08-13T05:35:00Z',
          },
        ],
      });
    const screen = await render(
      <DashboardScreen
        profileService={fakeProfileService}
        activeSessionService={{ listMyActiveSessions }}
        dashboardService={createEmptyDashboardService()}
      />,
    );

    expect(
      await screen.findByRole('button', { name: 'Start attendance' }),
    ).toBeTruthy();

    await act(async () => {
      mockFocusCallback?.();
    });

    expect(
      await screen.findByRole('button', { name: 'View progress' }),
    ).toBeTruthy();
    expect(listMyActiveSessions).toHaveBeenCalledTimes(2);
  });

  test('shows an error instead of mock active-session data after an API failure', async () => {
    const dashboardService: DashboardService = {
      async getUpcomingLectures() {
        return [];
      },
      async getActiveAttendanceSession() {
        return {
          id: 'mock-session-that-must-not-render',
          lectureId: 'mock-lecture',
          courseCode: 'MOCK101',
          courseName: 'Mock course',
          startTime: '2026-08-13T05:25:00Z',
          endTime: '2026-08-13T06:00:00Z',
          lateThreshold: '2026-08-13T05:45:00Z',
          checkInStatus: 'open',
          sessionTitle: 'Mock active session',
        };
      },
    };
    const activeSessionService: ActiveAttendanceSessionService = {
      async listMyActiveSessions() {
        return { status: 'network-error' };
      },
    };

    const { findByText, queryByText } = await render(
      <DashboardScreen
        profileService={fakeProfileService}
        activeSessionService={activeSessionService}
        dashboardService={dashboardService}
      />,
    );

    expect(await findByText('Dashboard could not be loaded')).toBeTruthy();
    expect(queryByText('Mock active session')).toBeNull();
  });

  test('shows the readiness button when a check is required', async () => {
    const faceVerificationApiService = createReadinessService(true);
    const onReadinessCheckPress = jest.fn();

    const { findByRole } = await render(
      <DashboardScreen
        profileService={fakeProfileService}
        dashboardService={createEmptyDashboardService()}
        faceVerificationApiService={faceVerificationApiService}
        onReadinessCheckPress={onReadinessCheckPress}
      />,
    );

    const readinessButton = await findByRole('button', {
        name: 'Check Face Verification Readiness',
      });
    fireEvent.press(readinessButton);

    expect(onReadinessCheckPress).toHaveBeenCalledTimes(1);
    expect(
      faceVerificationApiService.getReadinessStatus,
    ).toHaveBeenCalledTimes(1);
  });

  test('hides the readiness button when a check is not required', async () => {
    const faceVerificationApiService = createReadinessService(false);

    const { findByText, queryByRole } = await render(
      <DashboardScreen
        profileService={fakeProfileService}
        dashboardService={createEmptyDashboardService()}
        faceVerificationApiService={faceVerificationApiService}
      />,
    );

    expect(await findByText('No upcoming attendance')).toBeTruthy();
    expect(
      queryByRole('button', {
        name: 'Check Face Verification Readiness',
      }),
    ).toBeNull();
  });

  test('removes the readiness button when the dashboard regains focus after a passed check', async () => {
    const getReadinessStatus =
      jest.fn<FaceVerificationApiService['getReadinessStatus']>();
    getReadinessStatus
      .mockResolvedValueOnce({
        status: 'loaded',
        readiness: {
          status: 'not_checked',
          requiresReadinessCheck: true,
          checkedAt: null,
        },
      })
      .mockResolvedValueOnce({
        status: 'loaded',
        readiness: {
          status: 'passed',
          requiresReadinessCheck: false,
          checkedAt: '2026-08-28T08:30:00Z',
        },
      });
    const screen = await render(
      <DashboardScreen
        profileService={fakeProfileService}
        dashboardService={createEmptyDashboardService()}
        faceVerificationApiService={{ getReadinessStatus }}
      />,
    );

    expect(
      await screen.findByRole('button', {
        name: 'Check Face Verification Readiness',
      }),
    ).toBeTruthy();

    await act(async () => {
      mockFocusCallback?.();
    });

    await waitFor(() => {
      expect(
        screen.queryByRole('button', {
          name: 'Check Face Verification Readiness',
        }),
      ).toBeNull();
    });
    expect(getReadinessStatus).toHaveBeenCalledTimes(2);
  });

  test('opens the profile screen from the avatar action', async () => {
    const fakeService: DashboardService = {
      async getUpcomingLectures() {
        return [];
      },
      async getActiveAttendanceSession() {
        return null;
      },
    };

    const { findByRole } = await render(<DashboardScreen profileService={fakeProfileService} dashboardService={fakeService} />);

    fireEvent.press(await findByRole('button', { name: 'Open student profile' }));

    expect(mockPush).toHaveBeenCalledWith('/(student)/(tabs)/profile');
  });
});

function createEmptyDashboardService(): DashboardService {
  return {
    async getUpcomingLectures() {
      return [];
    },
    async getActiveAttendanceSession() {
      return null;
    },
  };
}

function createReadinessService(
  requiresReadinessCheck: boolean,
): Pick<FaceVerificationApiService, 'getReadinessStatus'> {
  const readinessStatus = requiresReadinessCheck
    ? ('not_checked' as const)
    : ('passed' as const);

  return {
    getReadinessStatus: jest.fn(async () => ({
      status: 'loaded' as const,
      readiness: {
        status: readinessStatus,
        requiresReadinessCheck,
        checkedAt: null,
      },
    })),
  };
}

function buildActiveSession(id: string, sessionTitle: string) {
  return {
    id,
    courseCode: 'CS3203',
    courseName: 'Software Engineering Project',
    sessionTitle,
    sessionType: 'lecture',
    scheduledStartAt: '2026-08-13T05:25:00Z',
    scheduledEndAt: '2026-08-13T06:30:00Z',
    checkInOpensAt: '2026-08-13T05:28:00Z',
    checkInClosesAt: '2026-08-13T06:00:00Z',
    lateAfterAt: '2026-08-13T05:45:00Z',
    venue: 'LH-02',
    requiresFaceVerification: true,
    requiresGeofence: true,
    requiresQr: false,
    attemptStatus: null,
    initialCheckInStatus: null,
    checkedInAt: null,
    finalAttendanceStatus: null,
  };
}
