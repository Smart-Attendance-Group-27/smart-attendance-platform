export type NotificationItem = {
  id: string;
  title: string;
  message: string;
  type:
    | 'attendance'
    | 'qr_session'
    | 'attendance_update'
    | 'general';
  createdAt: string;
  isRead: boolean;
  relatedId?: string;
};
