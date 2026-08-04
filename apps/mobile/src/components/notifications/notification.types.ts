export type NotificationCategory = 'attendance' | 'system';

export type NotificationVariant =
  | 'info'
  | 'success'
  | 'warning'
  | 'error';

export type NotificationIcon =
  | 'clock'
  | 'qr-code'
  | 'check-circle'
  | 'warning-triangle'
  | 'error-circle'
  | 'location';

export type StudentNotification = {
  id: string;
  title: string;
  description: string;
  timeLabel: string;
  category: NotificationCategory;
  variant: NotificationVariant;
  icon: NotificationIcon;
  isRead: boolean;
};

export type NotificationFilter = 'all' | NotificationCategory;
