import { describe, expect, jest, test } from '@jest/globals';

import type { CoreApiClient } from '../../../services/api/coreApiClient';
import { CoreApiNotificationPreferencesService } from '../services/notificationPreferencesService';

const preference = {
  typeCode: 'UPCOMING_CLASS',
  description: 'Upcoming class',
  inAppEnabled: true,
  pushEnabled: false,
  isCustomized: false,
};

describe('CoreApiNotificationPreferencesService', () => {
  test('loads effective preferences', async () => {
    const client = {
      get: jest.fn(async () => ({ status: 'ok', data: [preference] })),
    } as unknown as CoreApiClient;
    const service = new CoreApiNotificationPreferencesService(client);
    await expect(service.getPreferences()).resolves.toEqual([preference]);
  });

  test('saves channel values', async () => {
    const put = jest.fn(async () => ({
      status: 'ok',
      data: [{ ...preference, pushEnabled: true, isCustomized: true }],
    }));
    const client = { put } as unknown as CoreApiClient;
    const service = new CoreApiNotificationPreferencesService(client);

    const updated = await service.updatePreferences([
      { ...preference, pushEnabled: true },
    ]);

    expect(updated[0].pushEnabled).toBe(true);
    expect(put).toHaveBeenCalledWith(
      '/api/v1/students/me/notification-preferences',
      {
        preferences: [{
          typeCode: 'UPCOMING_CLASS',
          inAppEnabled: true,
          pushEnabled: true,
        }],
      },
    );
  });
});
