import {
  describe,
  expect,
  test,
} from '@jest/globals';

import {
  hasAuthRole,
  studentMobileRole,
  toAuthRoles,
} from '../utils/authRoles';

describe('auth role utilities', () => {
  test('keeps only UniAttend auth roles in a stable order', () => {
    expect(
      toAuthRoles([
        'offline_access',
        'administrator',
        'student',
        'student',
      ]),
    ).toEqual([
      'student',
      'administrator',
    ]);
  });

  test('checks whether an authenticated session has a role', () => {
    expect(
      hasAuthRole(
        {
          status: 'authenticated',
          userId: 'student-user-1',
          roles: ['student'],
        },
        studentMobileRole,
      ),
    ).toBe(true);

    expect(
      hasAuthRole(
        {
          status: 'unauthenticated',
        },
        studentMobileRole,
      ),
    ).toBe(false);
  });
});
