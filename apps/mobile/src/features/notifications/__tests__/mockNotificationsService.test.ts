import { describe, expect, test } from '@jest/globals';

import { MockNotificationsService } from '../services/mockNotificationsService';

const ISO_8601_PATTERN =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?(?:Z|[+-]\d{2}:\d{2})$/;

describe('MockNotificationsService', () => {
  test('returns populated notification data for the success scenario', async () => {
    const service = new MockNotificationsService();

    const notifications = await service.getNotifications();

    expect(notifications.length).toBeGreaterThan(0);
    expect(notifications).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ type: 'attendance' }),
        expect.objectContaining({ type: 'attendance_update' }),
        expect.objectContaining({ type: 'general' }),
      ]),
    );
  });

  test('includes QR-session notification data without defining QR actions', async () => {
    const service = new MockNotificationsService();

    const notifications = await service.getNotifications();
    const qrNotification = notifications.find(
      (notification) => notification.type === 'qr_session',
    );

    expect(qrNotification).toEqual(
      expect.objectContaining({
        id: 'qr-open',
        relatedId: 'qr-session-active',
        type: 'qr_session',
      }),
    );
  });

  test('returns an empty list for the empty scenario', async () => {
    const service = new MockNotificationsService({ initialNotifications: [] });

    await expect(service.getNotifications()).resolves.toEqual([]);
  });

  test('rejects reads and updates for the failure scenario', async () => {
    const service = new MockNotificationsService({ simulateFailure: true });

    await expect(service.getNotifications()).rejects.toThrow(
      'Mock notifications request failed',
    );
    await expect(service.markAsRead('attendance-opening')).rejects.toThrow(
      'Mock notifications request failed',
    );
  });

  test('marks only the selected notification as read', async () => {
    const service = new MockNotificationsService();

    await service.markAsRead('attendance-opening');
    const notifications = await service.getNotifications();

    expect(
      notifications.find(
        (notification) => notification.id === 'attendance-opening',
      )?.isRead,
    ).toBe(true);
    expect(
      notifications.find((notification) => notification.id === 'qr-open')
        ?.isRead,
    ).toBe(false);
  });

  test('returns independent values so callers cannot mutate service state', async () => {
    const service = new MockNotificationsService();
    const firstResult = await service.getNotifications();

    firstResult[0].title = 'Changed outside the service';
    const secondResult = await service.getNotifications();

    expect(secondResult[0].title).toBe('Attendance opens in 10 minutes');
  });

  test('uses valid ISO 8601 timestamps for every notification', async () => {
    const service = new MockNotificationsService();
    const notifications = await service.getNotifications();

    for (const notification of notifications) {
      expect(notification.createdAt).toMatch(ISO_8601_PATTERN);
      expect(Number.isNaN(Date.parse(notification.createdAt))).toBe(false);
    }
  });
});
