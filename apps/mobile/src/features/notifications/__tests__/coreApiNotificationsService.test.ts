import { describe, expect, jest, test } from '@jest/globals';
import type { CoreApiClient } from '../../../services/api/coreApiClient';
import { CoreApiNotificationsService } from '../services/coreApiNotificationsService';

const item = {
  id: 'notification-1', title: 'QR active', message: 'Scan now',
  type: 'qr_session', code: 'QR_SESSION_ACTIVE',
  createdAt: '2026-09-25T12:00:00Z', isRead: false,
  relatedId: 'session-1', relatedEntityType: 'ATTENDANCE_SESSION',
};

describe('CoreApiNotificationsService', () => {
  test('parses a page and calls the single read-all endpoint', async () => {
    const get = jest.fn(async (path: string) => ({
      status: 'ok',
      data: path.includes('unread-count') ? { unreadCount: 3 } :
        { items: [item], nextOffset: 30, unreadCount: 3 },
    }));
    const post = jest.fn(async () => ({ status: 'ok', data: { updated: 3 } }));
    const service = new CoreApiNotificationsService(
      { get, post } as unknown as CoreApiClient,
    );

    await expect(service.getPage(0, 30)).resolves.toEqual({
      items: [item], nextOffset: 30, unreadCount: 3,
    });
    await expect(service.getUnreadCount()).resolves.toBe(3);
    await service.markAllAsRead();
    expect(get).toHaveBeenCalledWith('/api/v1/students/me/notifications/page?offset=0&limit=30');
    expect(post).toHaveBeenCalledWith('/api/v1/students/me/notifications/read-all', {});
  });

  test('rejects malformed notification pages', async () => {
    const service = new CoreApiNotificationsService({
      get: jest.fn(async () => ({ status: 'ok', data: { items: [{}], nextOffset: null, unreadCount: 1 } })),
    } as unknown as CoreApiClient);
    await expect(service.getPage(0, 30)).rejects.toThrow('invalid');
  });
});
