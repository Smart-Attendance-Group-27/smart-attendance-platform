import { describe, expect, test } from '@jest/globals';
import React from 'react';
import { render } from '@testing-library/react-native';

import { CourseScreen } from '../screens/CourseScreen';
import { mockCourses } from '../mockCoursesData';
import type { CourseService } from '../services/courseService';

const fakeCourseService: CourseService = {
  async listMyCourses() {
    return { status: 'loaded', courses: mockCourses };
  },
};

describe('CourseScreen', () => {
  test('renders header and course list', async () => {
    const { findByText, findByPlaceholderText } = await render(
      <CourseScreen courseService={fakeCourseService} />,
    );

    expect(await findByText('Courses')).toBeTruthy();
    expect(await findByPlaceholderText('Search by course name or code')).toBeTruthy();
    expect(await findByText(/CS3203/)).toBeTruthy();
  });
});
