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
});
