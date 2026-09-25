import { describe, expect, jest, test } from '@jest/globals';
import { fireEvent, render } from '@testing-library/react-native';

import { mockCourses, type Course } from '../mockCoursesData';
import { CourseDetailsScreen } from '../screens/CourseDetailsScreen';

const course: Course = {
  ...mockCourses[0],
  id: 'history-test',
  attendedSessions: 2,
  totalSessions: 3,
  attendancePercentage: 67,
  sessions: ['marked', 'late', 'absent', 'cancelled', 'awaiting'].map((status, index) => ({
    id: `session-${index}`,
    title: `Session ${index + 1}`,
    type: 'Lecture' as const,
    timeText: '10:00-11:00',
    startsAt: '2026-09-20T04:30:00.000Z',
    endsAt: '2026-09-20T05:30:00.000Z',
    venue: null,
    status: status as Course['sessions'][number]['status'],
  })),
  attendanceRecords: ['Present', 'Late', 'Absent', 'Cancelled', 'Awaiting'].map((status, index) => ({
    id: `record-${index}`,
    day: '20',
    month: 'SEP',
    title: `Session ${index + 1}`,
    recordedText: 'Result',
    status: status as Course['attendanceRecords'][number]['status'],
  })),
};

describe('CourseDetailsScreen', () => {
  test('shows final and awaiting states without a simulation toggle', async () => {
    const screen = await render(<CourseDetailsScreen
      courses={[course]}
      courseId={course.id}
      onBack={jest.fn()}
    />);

    expect(screen.getByText('Present')).toBeTruthy();
    expect(screen.getByText('Late')).toBeTruthy();
    expect(screen.getByText('Absent')).toBeTruthy();
    expect(screen.getByText('Cancelled')).toBeTruthy();
    expect(screen.getByText('Awaiting result')).toBeTruthy();
    expect(screen.queryByText(/Toggle to/)).toBeNull();

    await fireEvent.press(screen.getByText('Attendance'));
    expect(screen.getByText('Attended')).toBeTruthy();
    expect(screen.getAllByText('Late')).toHaveLength(1);
    expect(screen.getAllByText('Cancelled')).toHaveLength(1);
    expect(screen.getAllByText('Awaiting')).toHaveLength(1);
  });

  test('shows the own attendance target of the course instead of a fixed one', async () => {
    const screen = await render(<CourseDetailsScreen
      courses={[{ ...course, attendanceThresholdPercent: 75 }]}
      courseId={course.id}
      onBack={jest.fn()}
    />);

    await fireEvent.press(screen.getByText('Attendance'));

    expect(screen.getByText('Current attendance · Target 75%')).toBeTruthy();
    expect(screen.queryByText(/Target 80%/)).toBeNull();
  });

  test('does not show 0% or a target for a course with no completed sessions', async () => {
    const screen = await render(<CourseDetailsScreen
      courses={[{ ...course, attendancePercentage: null, attendedSessions: 0, totalSessions: 0 }]}
      courseId={course.id}
      onBack={jest.fn()}
    />);

    await fireEvent.press(screen.getByText('Attendance'));

    expect(screen.getByText('No completed sessions yet')).toBeTruthy();
    expect(screen.queryByText('0%')).toBeNull();
  });
});
