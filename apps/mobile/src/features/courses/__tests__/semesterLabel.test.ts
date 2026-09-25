import { describe, expect, test } from '@jest/globals';

import { getCommonSemester } from '../utils/semesterLabel';

describe('getCommonSemester', () => {
  test('returns the semester shared by every course', () => {
    expect(getCommonSemester([{ semester: 'Semester 2, 2026' }, { semester: 'Semester 2, 2026' }])).toBe(
      'Semester 2, 2026',
    );
  });

  test('returns null when courses span several semesters or there are none', () => {
    expect(getCommonSemester([{ semester: 'Semester 1, 2026' }, { semester: 'Semester 2, 2026' }])).toBeNull();
    expect(getCommonSemester([])).toBeNull();
    expect(getCommonSemester([{ semester: ' ' }])).toBeNull();
  });
});
