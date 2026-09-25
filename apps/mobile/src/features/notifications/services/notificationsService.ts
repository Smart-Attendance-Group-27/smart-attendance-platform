import type { NotificationItem } from '../types/notification';

export interface NotificationsService {
  getNotifications(): Promise<NotificationItem[]>;
  getPage(offset: number, limit: number): Promise<NotificationPage>;
  getUnreadCount(): Promise<number>;
  markAsRead(notificationId: string): Promise<void>;
  markAllAsRead(): Promise<void>;
}

export type NotificationPage = {
  items: NotificationItem[];
  nextOffset: number | null;
  unreadCount: number;
};
