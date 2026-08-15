import { describe, expect, test } from '@jest/globals';
import React from 'react';
import { render } from '@testing-library/react-native';

import { CourseScreen } from '../screens/CourseScreen';

describe('CourseScreen', () => {
  test('renders header and course list', async () => {
    const { findByText } = await render(<CourseScreen />);

    expect(await findByText('My courses')).toBeTruthy();
    expect(await findByText('All courses')).toBeTruthy();
  });
});
