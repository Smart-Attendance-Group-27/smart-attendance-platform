import type { CoreApiClient } from '../../../services/api/coreApiClient';
import type { NotificationPreference } from '../types/notificationPreference';

const preferencesPath = '/api/v1/students/me/notification-preferences';

export interface NotificationPreferencesService {
  getPreferences(): Promise<NotificationPreference[]>;
  updatePreferences(
    preferences: NotificationPreference[],
  ): Promise<NotificationPreference[]>;
}

export class CoreApiNotificationPreferencesService
  implements NotificationPreferencesService
{
  constructor(private readonly client: CoreApiClient) {}

  async getPreferences(): Promise<NotificationPreference[]> {
    const result = await this.client.get<unknown>(preferencesPath);
    if (result.status !== 'ok' || !Array.isArray(result.data)) {
      throw new Error(`Notification preferences request failed: ${result.status}`);
    }
    return result.data.map(parsePreference);
  }

  async updatePreferences(
    preferences: NotificationPreference[],
  ): Promise<NotificationPreference[]> {
    const result = await this.client.put<unknown>(preferencesPath, {
      preferences: preferences.map((preference) => ({
        typeCode: preference.typeCode,
        inAppEnabled: preference.inAppEnabled,
        pushEnabled: preference.pushEnabled,
      })),
    });
    if (result.status !== 'ok' || !Array.isArray(result.data)) {
      throw new Error(`Notification preferences update failed: ${result.status}`);
    }
    return result.data.map(parsePreference);
  }
}

function parsePreference(value: unknown): NotificationPreference {
  if (!value || typeof value !== 'object') {
    throw new Error('Notification preference response was invalid.');
  }
  const item = value as Partial<NotificationPreference>;
  if (
    typeof item.typeCode !== 'string' ||
    typeof item.description !== 'string' ||
    typeof item.inAppEnabled !== 'boolean' ||
    typeof item.pushEnabled !== 'boolean' ||
    typeof item.isCustomized !== 'boolean'
  ) {
    throw new Error('Notification preference response was invalid.');
  }
  return item as NotificationPreference;
}
