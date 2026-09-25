import { describe, expect, test } from '@jest/globals';
import { StyleSheet } from 'react-native';
import { render } from '@testing-library/react-native';

import { COURSE_CARD_HEIGHT, CourseSummaryCard } from '../CourseSummaryCard';

const course = {
  code: 'CS3203',
  title: 'A very long course title that would normally wrap across several lines on a narrow card',
  lecturer: 'Dr. N. Perera',
  attendancePercentage: 82,
  upcomingSessions: 2,
  color: '#173B7A',
};

describe('CourseSummaryCard', () => {
  test('has a fixed height so every card on the home rail is the same size', async () => {
    const short = await render(<CourseSummaryCard course={{ ...course, title: 'Databases' }} />);
    const long = await render(<CourseSummaryCard course={course} />);

    const heightOf = (screen: typeof short) =>
      StyleSheet.flatten(screen.getByTestId('course-summary-card').props.style).height;

    expect(heightOf(short)).toBe(COURSE_CARD_HEIGHT);
    expect(heightOf(long)).toBe(COURSE_CARD_HEIGHT);
  });

  test('shows a dash and "No sessions yet" instead of 0% for a course with no data', async () => {
    const screen = await render(<CourseSummaryCard course={{ ...course, attendancePercentage: null }} />);

    expect(screen.getByText('—')).toBeTruthy();
    expect(screen.getByText('No sessions yet')).toBeTruthy();
    expect(screen.queryByText('0%')).toBeNull();
  });

  test('shows the percentage when there is data', async () => {
    const screen = await render(<CourseSummaryCard course={course} />);

    expect(screen.getByText('82%')).toBeTruthy();
    expect(screen.getByText('Attendance')).toBeTruthy();
  });
});
