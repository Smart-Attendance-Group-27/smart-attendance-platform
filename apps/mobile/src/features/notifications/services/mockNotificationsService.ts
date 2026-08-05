import type { NotificationItem } from '../types/notification';
import type { NotificationsService } from './notificationsService';

export type MockNotificationsServiceOptions = {
  readonly initialNotifications?: readonly NotificationItem[];
  readonly simulateFailure?: boolean;
};

const defaultNotifications: readonly NotificationItem[] = [
  {
    id: 'attendance-opening',
    title: 'Attendance opens in 10 minutes',
    message: 'CS3203 - Architecture Review Lecture',
    type: 'attendance',
    createdAt: '2026-08-05T09:50:00+05:30',
    isRead: false,
    relatedId: 'attendance-session-active',
  },
  {
    id: 'qr-open',
    title: 'QR attendance is now open',
    message: 'MA3030 - Operational Research',
    type: 'qr_session',
    createdAt: '2026-08-05T13:02:00+05:30',
    isRead: false,
    relatedId: 'qr-session-active',
  },
  {
    id: 'attendance-recorded',
    title: 'Attendance recorded successfully',
    message: 'CS3052 - Network Defence Lab',
    type: 'attendance_update',
    createdAt: '2026-08-04T08:12:00+05:30',
    isRead: true,
    relatedId: 'attendance-session-closed',
  },
  {
    id: 'attendance-missed',
    title: 'You missed the CS3052 attendance session',
    message: 'Computer Security - 14 Jul',
    type: 'attendance_update',
    createdAt: '2026-08-03T10:05:00+05:30',
    isRead: true,
    relatedId: 'attendance-session-closed',
  },
  {
    id: 'attendance-low',
    title: 'Your attendance in MA3030 has fallen below 80%',
    message: 'Operational Research',
    type: 'general',
    createdAt: '2026-08-02T11:30:00+05:30',
    isRead: true,
  },
  {
    id: 'location-changed',
    title: 'Attendance location changed to Lecture Hall 02',
    message: 'CS3203 - Software Engineering Project',
    type: 'general',
    createdAt: '2026-08-01T15:45:00+05:30',
    isRead: true,
    relatedId: 'attendance-session-active',
  },
];

const cloneNotification = (
  notification: NotificationItem,
): NotificationItem => ({ ...notification });

export class MockNotificationsService implements NotificationsService {
  private notifications: NotificationItem[];

  private readonly simulateFailure: boolean;

  constructor({
    initialNotifications = defaultNotifications,
    simulateFailure = false,
  }: MockNotificationsServiceOptions = {}) {
    this.notifications = initialNotifications.map(cloneNotification);
    this.simulateFailure = simulateFailure;
  }

  async getNotifications(): Promise<NotificationItem[]> {
    this.throwIfFailureIsEnabled();

    return this.notifications.map(cloneNotification);
  }

  async markAsRead(notificationId: string): Promise<void> {
    this.throwIfFailureIsEnabled();

    this.notifications = this.notifications.map((notification) =>
      notification.id === notificationId
        ? { ...notification, isRead: true }
        : notification,
    );
  }

  private throwIfFailureIsEnabled(): void {
    if (this.simulateFailure) {
      throw new Error('Mock notifications request failed');
    }
  }
}
