import { describe, expect, jest, test } from '@jest/globals';

import {
  destinationForNotificationData,
  installNotificationNavigation,
} from '../services/notificationNavigation';

describe('notification navigation', () => {
  test.each(['ATTENDANCE_SESSION', 'attendance_session', 'Attendance_Session'])(
    'opens the attendance progress screen for %s',
    (relatedEntityType: string) => {
      expect(destinationForNotificationData({
        notificationId: 'notification-1',
        relatedEntityType,
        relatedEntityId: 'session-1',
      })).toBe('/(student)/attendance/session-1/progress');
    },
  );

  test('falls back to notifications when related session data is absent', () => {
    expect(destinationForNotificationData({ notificationId: 'notification-1' }))
      .toBe('/(student)/(tabs)/notifications');
  });

  test('handles the cold-start notification response', async () => {
    const navigate = jest.fn();
    const response = {
      notification: {
        request: {
          content: {
            data: {
              relatedEntityType: 'attendance_session',
              relatedEntityId: 'session-cold',
            },
          },
        },
      },
    } as never;
    const remove = jest.fn();
    const clearLastNotificationResponseAsync = jest.fn(async () => undefined);
    const api = {
      addNotificationResponseReceivedListener: jest.fn(() => ({ remove })),
      getLastNotificationResponseAsync: jest.fn(async () => response),
      clearLastNotificationResponseAsync,
    } as never;

    const cleanup = installNotificationNavigation(navigate, api);
    await Promise.resolve();

    expect(navigate).toHaveBeenCalledWith(
      '/(student)/attendance/session-cold/progress',
    );
    expect(clearLastNotificationResponseAsync).toHaveBeenCalled();
    cleanup();
    expect(remove).toHaveBeenCalled();
  });
});
