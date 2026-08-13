import { beforeEach, describe, expect, jest, test } from '@jest/globals';
import { fireEvent, render } from '@testing-library/react-native';

import { DashboardScreen } from '../screens/DashboardScreen';
import type { ActiveAttendanceSessionService } from '../services/activeAttendanceSessionService';
import type { DashboardService } from '../services/dashboardService';

const mockPush = jest.fn();

jest.mock('expo-router', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

describe('DashboardScreen', () => {
  beforeEach(() => {
    mockPush.mockClear();
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

    const { findByText } = await render(<DashboardScreen dashboardService={fakeService} />);

    expect(await findByText(/CS101.*Intro/)).toBeTruthy();
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

    const { findByText } = await render(<DashboardScreen dashboardService={fakeService} />);

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

    const { findByText, findByLabelText } = await render(<DashboardScreen dashboardService={fakeService} />);

    expect(await findByText('Dashboard could not be loaded')).toBeTruthy();
    expect(await findByLabelText('Retry dashboard')).toBeTruthy();
  });

  test('navigates to location check when Start pressed for active session', async () => {
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

    const { findByRole } = await render(<DashboardScreen dashboardService={fakeService} />);

    const startButton = await findByRole('button', { name: 'Start attendance' });

    fireEvent.press(startButton);

    expect(mockPush).toHaveBeenCalledWith({
      pathname: '/(student)/attendance/[sessionId]/location-check',
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
      pathname: '/(student)/attendance/[sessionId]/location-check',
      params: {
        sessionId: '40000000-0000-0000-0000-000000000002',
      },
    });
    expect(getActiveAttendanceSession).not.toHaveBeenCalled();
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
        activeSessionService={activeSessionService}
        dashboardService={dashboardService}
      />,
    );

    expect(await findByText('Dashboard could not be loaded')).toBeTruthy();
    expect(queryByText('Mock active session')).toBeNull();
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

    const { findByRole } = await render(<DashboardScreen dashboardService={fakeService} />);

    fireEvent.press(await findByRole('button', { name: 'Open student profile' }));

    expect(mockPush).toHaveBeenCalledWith('/(student)/(tabs)/profile');
  });
});

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
  };
}
