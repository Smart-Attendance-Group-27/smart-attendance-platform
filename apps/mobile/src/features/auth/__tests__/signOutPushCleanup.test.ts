import { describe, expect, jest, test } from '@jest/globals';

import { revokePushBeforeSignOut } from '../services/signOutPushCleanup';

jest.mock('expo-notifications', () => ({
  setNotificationHandler: jest.fn(),
  getExpoPushTokenAsync: jest.fn(),
}), { virtual: true });

describe('sign-out push cleanup', () => {
  test('revokes with an authenticated API client', async () => {
    const revoke = jest.fn(async () => true);
    await revokePushBeforeSignOut('access-token', revoke);
    expect(revoke).toHaveBeenCalledTimes(1);
  });

  test('does not reject when revocation fails', async () => {
    const revoke = jest.fn(async () => {
      throw new Error('offline');
    });
    await expect(revokePushBeforeSignOut('access-token', revoke)).resolves.toBeUndefined();
  });
});
