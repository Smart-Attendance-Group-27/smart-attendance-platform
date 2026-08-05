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

    return [
      {
        id: 'lecture-1',
        courseId: 'course-1',
        courseCode: 'CS3202',
        courseName: 'Software Engineering',
        startTime: new Date(Date.now() + 3600000).toISOString(), 
        endTime: new Date(Date.now() + 7200000).toISOString(),
        venue: 'Hall A',
      }
    ];
  }

  async getActiveAttendanceSession(): Promise<AttendanceSession | null> {
    return null; 
  }
}