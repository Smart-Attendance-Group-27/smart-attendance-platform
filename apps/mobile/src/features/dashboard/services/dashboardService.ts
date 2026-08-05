import { Lecture, AttendanceSession } from '../types';

export interface DashboardService {
  getUpcomingLectures(): Promise<Lecture[]>;
  getActiveAttendanceSession(): Promise<AttendanceSession | null>;
}