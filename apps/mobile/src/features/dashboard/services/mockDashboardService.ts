import { DashboardService } from './dashboardService';
import { Lecture, AttendanceSession } from '../types';

// We define a type for our simulation states
type MockState = 'success' | 'empty' | 'error';

export class MockDashboardService implements DashboardService {
  private state: MockState;

  // The constructor defaults to 'success' so our first test still passes!
  constructor(state: MockState = 'success') {
    this.state = state;
  }

  async getUpcomingLectures(): Promise<Lecture[]> {
    if (this.state === 'error') {
      throw new Error('Failed to fetch dashboard data');
    }

    if (this.state === 'empty') {
      return [];
    }

    // Return several upcoming lectures spaced across the next days for scrolling
    const now = Date.now();
    const lectures: Lecture[] = [
      {
        id: 'lecture-cs3203-1',
        courseId: 'cs3203',
        courseCode: 'CS3203',
        courseName: 'Software Engineering Project',
        startTime: new Date(now + 3600 * 1000).toISOString(),
        endTime: new Date(now + 7200 * 1000).toISOString(),
        venue: 'Hall 02',
      },
      {
        id: 'lecture-ma3030-1',
        courseId: 'ma3030',
        courseCode: 'MA3030',
        courseName: 'Operational Research',
        startTime: new Date(now + 24 * 3600 * 1000).toISOString(),
        endTime: new Date(now + 25 * 3600 * 1000).toISOString(),
        venue: 'Room B4',
      },
      {
        id: 'lecture-cs3052-1',
        courseId: 'cs3052',
        courseCode: 'CS3052',
        courseName: 'Computer Security',
        startTime: new Date(now + 48 * 3600 * 1000).toISOString(),
        endTime: new Date(now + 50 * 3600 * 1000).toISOString(),
        venue: 'Lab 3',
      },
      {
        id: 'lecture-cs2101-1',
        courseId: 'cs2101',
        courseCode: 'CS2101',
        courseName: 'Data Structures',
        startTime: new Date(now + 72 * 3600 * 1000).toISOString(),
        endTime: new Date(now + 74 * 3600 * 1000).toISOString(),
        venue: 'Room C1',
      },
    ];

    return lectures;
  }

  async getActiveAttendanceSession(): Promise<AttendanceSession | null> {
    if (this.state === 'success') {
      return {
        id: 'attendance-session-active',
        lectureId: 'lecture-cs3203-1',
        courseCode: 'CS3203',
        courseName: 'Software Engineering Project',
        startTime: new Date(Date.now() - 15 * 60000).toISOString(),
        endTime: new Date(Date.now() + 45 * 60000).toISOString(),
        lateThreshold: new Date(Date.now() + 10 * 60000).toISOString(),
        checkInStatus: 'open',
        sessionTitle: 'Architecture Review Lecture',
        venue: 'Lecture Hall 02',
      };
    }

    return null;
  }
}