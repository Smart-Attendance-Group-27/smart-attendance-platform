import type { CoreApiClient } from '../../../services/api/coreApiClient';
import type { NotificationItem } from '../types/notification';
import type { NotificationsService } from './notificationsService';

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

  async markAsRead(notificationId: string): Promise<void> {
    const result = await this.coreApiClient.post<unknown>(
      `${notificationsPath}/${notificationId}/read`,
      {},
    );

    if (result.status !== 'ok') {
      throw new Error(`Mark notification read failed: ${result.status}`);
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
