import { CoreApiClient } from '../../../services/api/coreApiClient';
import { revokePushNotifications } from '../../notifications/services/pushNotificationService';

type Revoke = (client: CoreApiClient) => Promise<boolean>;

export async function revokePushBeforeSignOut(
  accessToken: string,
  revoke: Revoke = revokePushNotifications,
): Promise<void> {
  try {
    await revoke(new CoreApiClient({ getAccessToken: () => accessToken }));
  } catch {
    // Local and Keycloak logout must continue even when push cleanup fails.
  }
}
