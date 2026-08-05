import type { NotificationItem } from '../types/notification';

export interface NotificationsService {
  getNotifications(): Promise<NotificationItem[]>;
  markAsRead(notificationId: string): Promise<void>;
}
