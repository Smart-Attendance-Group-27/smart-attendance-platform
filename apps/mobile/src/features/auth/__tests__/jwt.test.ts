import {
  describe,
  expect,
  test,
} from '@jest/globals';

import {
  getJwtRoles,
  getJwtSubject,
} from '../utils/jwt';

describe('jwt utilities', () => {
  test('reads the subject from a JWT payload', () => {
    expect(getJwtSubject(buildToken({ sub: 'keycloak-user-1' }))).toBe(
      'keycloak-user-1',
    );
  });

  test('reads realm and client roles from a Keycloak JWT payload', () => {
    const token = buildToken({
      realm_access: {
        roles: [
          'student',
          'offline_access',
          42,
        ],
      },
      resource_access: {
        'other-client': {
          roles: ['administrator'],
        },
        'uniattend-mobile': {
          roles: [
            'student',
            'lecturer',
          ],
        },
      },
    });

    expect(getJwtRoles(token, 'uniattend-mobile')).toEqual([
      'student',
      'offline_access',
      'lecturer',
    ]);
  });

  test('returns empty values for missing or malformed JWT payloads', () => {
    expect(getJwtSubject()).toBeNull();
    expect(getJwtSubject('not-a-token')).toBeNull();
    expect(getJwtRoles('not-a-token', 'uniattend-mobile')).toEqual([]);
  });
});

function buildToken(payload: Record<string, unknown>) {
  return `header.${toBase64Url(JSON.stringify(payload))}.signature`;
}

function toBase64Url(value: string) {
  return btoa(value).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
