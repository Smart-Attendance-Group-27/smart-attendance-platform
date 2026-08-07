import {
  describe,
  expect,
  test,
} from '@jest/globals';

import { MockAuthService } from '../services/mockAuthService';

describe('MockAuthService', () => {
  test('starts unauthenticated by default', async () => {
    const service = new MockAuthService();

    await expect(service.restoreSession()).resolves.toEqual({
      status: 'unauthenticated',
    });
  });

  test('starts authenticated when configured with an authenticated session', async () => {
    const service = new MockAuthService({
      initialSession: {
        status: 'authenticated',
        userId: 'configured-student-user',
        roles: ['student'],
      },
    });

    await expect(service.restoreSession()).resolves.toEqual({
      status: 'authenticated',
      userId: 'configured-student-user',
      roles: ['student'],
    });
  });

  test('signs in successfully with the configured mock user id', async () => {
    const service = new MockAuthService({
      authenticatedUserId: 'signed-in-student-user',
    });

    await expect(service.signIn()).resolves.toEqual({
      success: true,
      session: {
        status: 'authenticated',
        userId: 'signed-in-student-user',
        roles: ['student'],
      },
    });
  });

  test('simulates sign-in failure without authenticating the session', async () => {
    const service = new MockAuthService({
      simulateSignInFailure: true,
    });

    await expect(service.signIn()).resolves.toEqual({
      success: false,
    });
    await expect(service.restoreSession()).resolves.toEqual({
      status: 'unauthenticated',
    });
  });

  test('restores an authenticated session after successful sign-in', async () => {
    const service = new MockAuthService({
      authenticatedUserId: 'restored-student-user',
    });

    await service.signIn();

    await expect(service.restoreSession()).resolves.toEqual({
      status: 'authenticated',
      userId: 'restored-student-user',
      roles: ['student'],
    });
  });

  test('restores an unauthenticated session after sign-out', async () => {
    const service = new MockAuthService({
      initialSession: {
        status: 'authenticated',
        userId: 'signed-out-student-user',
        roles: ['student'],
      },
    });

    await expect(service.signOut()).resolves.toEqual({
      status: 'unauthenticated',
    });
    await expect(service.restoreSession()).resolves.toEqual({
      status: 'unauthenticated',
    });
  });
});
