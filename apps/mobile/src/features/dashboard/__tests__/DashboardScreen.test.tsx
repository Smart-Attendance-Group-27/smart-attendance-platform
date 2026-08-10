import { beforeEach, describe, expect, jest, test } from '@jest/globals';
import { fireEvent, render } from '@testing-library/react-native';

import { DashboardScreen } from '../screens/DashboardScreen';
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
