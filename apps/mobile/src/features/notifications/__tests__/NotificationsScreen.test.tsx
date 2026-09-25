import { describe, expect, jest, test } from '@jest/globals';
import {
  fireEvent,
  render,
  waitFor,
} from '@testing-library/react-native';

import { NotificationsScreen } from '../screens/NotificationsScreen';
import { MockNotificationsService } from '../services/mockNotificationsService';

describe('NotificationsScreen', () => {
  test('renders notifications loaded by the service', async () => {
    const service = new MockNotificationsService();
    const { findByText } = await render(
      <NotificationsScreen notificationsService={service} />,
    );

    expect(await findByText('Attendance opens in 10 minutes')).toBeTruthy();
    expect(await findByText('QR attendance is now open')).toBeTruthy();
  });

  test('renders the empty state when the service returns no notifications', async () => {
    const service = new MockNotificationsService({ initialNotifications: [] });
    const { findByText } = await render(
      <NotificationsScreen notificationsService={service} />,
    );

    expect(await findByText('No notifications yet')).toBeTruthy();
  });

  test('renders the retry state when the service fails', async () => {
    const service = new MockNotificationsService({ simulateFailure: true });
    const { findByRole, findByText } = await render(
      <NotificationsScreen notificationsService={service} />,
    );

    expect(
      await findByText('Notifications could not be loaded'),
    ).toBeTruthy();
    expect(
      await findByRole('button', { name: 'Retry loading notifications' }),
    ).toBeTruthy();
  });

  test('asks the service to mark a selected notification as read', async () => {
    const service = new MockNotificationsService();
    const markAsRead = jest.spyOn(service, 'markAsRead');
    const { findByLabelText } = await render(
      <NotificationsScreen notificationsService={service} />,
    );
    const notification = await findByLabelText(
      /Attendance opens in 10 minutes.*Unread/,
    );

    await fireEvent.press(notification);

    await waitFor(() => {
      expect(markAsRead).toHaveBeenCalledWith('attendance-opening');
    });
  });

  test('opens the related screen after marking a notification read', async () => {
    const service = new MockNotificationsService();
    const onOpenNotification = jest.fn();
    const { findByLabelText } = await render(
      <NotificationsScreen notificationsService={service} onOpenNotification={onOpenNotification} />,
    );

    await fireEvent.press(await findByLabelText(/Attendance opens in 10 minutes.*Unread/));
    await waitFor(() => expect(onOpenNotification).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'attendance-opening' }),
    ));
  });

  test('marks all unread notifications with one service request', async () => {
    const service = new MockNotificationsService();
    const markAllAsRead = jest.spyOn(service, 'markAllAsRead');
    const { findByRole } = await render(
      <NotificationsScreen notificationsService={service} />,
    );

    await fireEvent.press(await findByRole('button', { name: 'Mark all notifications as read' }));
    await waitFor(() => expect(markAllAsRead).toHaveBeenCalledTimes(1));
    expect(await service.getUnreadCount()).toBe(0);
  });

  test('loads more notifications when the first page is full', async () => {
    const notifications = Array.from({ length: 31 }, (_, index) => ({
      id: `item-${index}`,
      title: `Notice ${index}`,
      message: 'Message',
      type: 'general' as const,
      createdAt: '2026-09-25T12:00:00Z',
      isRead: true,
    }));
    const service = new MockNotificationsService({ initialNotifications: notifications });
    const { findByRole, findByText, queryByText } = await render(
      <NotificationsScreen notificationsService={service} />,
    );

    expect(queryByText('Notice 30')).toBeNull();
    await fireEvent.press(await findByRole('button', { name: 'Load more notifications' }));
    expect(await findByText('Notice 30')).toBeTruthy();
  });
});
