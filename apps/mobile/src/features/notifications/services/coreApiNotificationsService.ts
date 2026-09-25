import type { CoreApiClient } from '../../../services/api/coreApiClient';
import type { NotificationItem } from '../types/notification';
import type { NotificationPage, NotificationsService } from './notificationsService';

const notificationsPath = '/api/v1/students/me/notifications';

type NotificationResponse = Partial<Record<keyof NotificationItem, unknown>>;

export class CoreApiNotificationsService implements NotificationsService {
  constructor(private readonly coreApiClient: CoreApiClient) {}

  async getNotifications(): Promise<NotificationItem[]> {
    const result = await this.coreApiClient.get<unknown>(notificationsPath);

    if (result.status !== 'ok') {
      throw new Error(`Notifications request failed: ${result.status}`);
    }

    if (!Array.isArray(result.data)) {
      throw new Error('Notifications response was invalid.');
    }

    const notifications = result.data.map(toNotificationItem);
    if (notifications.some((notification) => notification === null)) {
      throw new Error('Notifications response was invalid.');
    }

    return notifications as NotificationItem[];
  }

  async getPage(offset: number, limit: number): Promise<NotificationPage> {
    const result = await this.coreApiClient.get<unknown>(
      `${notificationsPath}/page?offset=${offset}&limit=${limit}`,
    );
    if (result.status !== 'ok' || !result.data || typeof result.data !== 'object') {
      throw new Error('Notifications page request failed.');
    }
    const page = result.data as Record<string, unknown>;
    if (!Array.isArray(page.items) || typeof page.unreadCount !== 'number' ||
      !(page.nextOffset === null || typeof page.nextOffset === 'number')) {
      throw new Error('Notifications page response was invalid.');
    }
    const items = page.items.map(toNotificationItem);
    if (items.some((item) => item === null)) {
      throw new Error('Notifications page response was invalid.');
    }
    return {
      items: items as NotificationItem[],
      nextOffset: page.nextOffset as number | null,
      unreadCount: page.unreadCount,
    };
  }

  async getUnreadCount(): Promise<number> {
    const result = await this.coreApiClient.get<unknown>(`${notificationsPath}/unread-count`);
    if (result.status !== 'ok' || !result.data || typeof result.data !== 'object' ||
      typeof (result.data as { unreadCount?: unknown }).unreadCount !== 'number') {
      throw new Error('Unread notification count request failed.');
    }
    return (result.data as { unreadCount: number }).unreadCount;
  }

  async markAsRead(notificationId: string): Promise<void> {
    const result = await this.coreApiClient.post<unknown>(
      `${notificationsPath}/${notificationId}/read`,
      {},
    );

    if (result.status !== 'ok') {
      throw new Error(`Mark notification read failed: ${result.status}`);
    }
  }

  async markAllAsRead(): Promise<void> {
    const result = await this.coreApiClient.post<unknown>(
      `${notificationsPath}/read-all`, {},
    );
    if (result.status !== 'ok') {
      throw new Error(`Mark all notifications read failed: ${result.status}`);
    }
  }
}

function toNotificationItem(value: unknown): NotificationItem | null {
  if (!value || typeof value !== 'object') {
    return null;
  }

  const response = value as NotificationResponse;
  if (
    typeof response.id !== 'string' ||
    typeof response.title !== 'string' ||
    typeof response.message !== 'string' ||
    !isNotificationType(response.type) ||
    typeof response.createdAt !== 'string' ||
    typeof response.isRead !== 'boolean'
  ) {
    return null;
  }

  return {
    id: response.id,
    title: response.title,
    message: response.message,
    type: response.type,
    createdAt: response.createdAt,
    isRead: response.isRead,
    relatedId:
      typeof response.relatedId === 'string' ? response.relatedId : undefined,
    relatedEntityType:
      typeof response.relatedEntityType === 'string'
        ? response.relatedEntityType
        : undefined,
    code: typeof response.code === 'string' ? response.code : undefined,
  };
}

function isNotificationType(value: unknown): value is NotificationItem['type'] {
  return (
    value === 'attendance' ||
    value === 'qr_session' ||
    value === 'attendance_update' ||
    value === 'general'
  );
}
