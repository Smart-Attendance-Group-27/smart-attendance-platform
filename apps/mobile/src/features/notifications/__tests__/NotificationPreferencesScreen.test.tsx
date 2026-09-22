import { fireEvent, render, waitFor } from '@testing-library/react-native';
import { describe, expect, jest, test } from '@jest/globals';

import { NotificationPreferencesScreen } from '../screens/NotificationPreferencesScreen';
import type { NotificationPreferencesService } from '../services/notificationPreferencesService';
import type { NotificationPreference } from '../types/notificationPreference';

describe('NotificationPreferencesScreen', () => {
  test('loads, toggles, and saves preferences', async () => {
    const preference = {
      typeCode: 'UPCOMING_CLASS',
      description: 'Upcoming class reminders',
      inAppEnabled: true,
      pushEnabled: false,
      isCustomized: false,
    };
    const updatePreferences = jest.fn(async (values: NotificationPreference[]) => values);
    const service = {
      getPreferences: jest.fn(async () => [preference]),
      updatePreferences,
    } as NotificationPreferencesService;

    const screen = await render(
      <NotificationPreferencesScreen onBack={jest.fn()} service={service} />,
    );

    expect(await screen.findByText('Upcoming class reminders')).toBeTruthy();
    await fireEvent(screen.getByLabelText('Push notifications'), 'valueChange', true);
    await fireEvent.press(screen.getByLabelText('Save notification preferences'));

    await waitFor(() => expect(updatePreferences).toHaveBeenCalledWith([
      expect.objectContaining({ pushEnabled: true }),
    ]));
  });
});
