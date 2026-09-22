/**
 * Push Notification Registration Service
 *
 * Responsibilities:
 *  1. Gate on physical device — Expo push tokens are unavailable on emulators.
 *  2. Request (or check) OS notification permission.
 *  3. Retrieve the project-scoped Expo push token.
 *  4. POST the token to the backend so the server can deliver push notifications.
 *
 * Call `registerForPushNotifications` once after the user is authenticated.
 * Calling it more than once is safe — the backend upserts the token.
 */

import Constants from 'expo-constants';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

import type { CoreApiClient } from '../../../services/api/coreApiClient';

const deviceRegistrationPath = '/api/v1/notifications/devices';

// Configure how notifications are presented when the app is in the foreground.
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldPlaySound: true,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

export type PushRegistrationResult =
  | { readonly status: 'registered' }
  | { readonly status: 'permission-denied' }
  | { readonly status: 'not-a-physical-device' }
  | { readonly status: 'error'; readonly reason: string };

/**
 * Request permission, obtain an Expo push token, and register it with the
 * backend.  Safe to call on every app launch — the backend upserts the token.
 */
export async function registerForPushNotifications(
  coreApiClient: CoreApiClient,
): Promise<PushRegistrationResult> {
  // Expo push tokens are only issued for physical devices.
  if (!Device.isDevice) {
    console.warn(
      '[PushNotifications] Push notifications are not available on the emulator.',
    );
    return { status: 'not-a-physical-device' };
  }

  // Android 13+ requires an explicit POST_NOTIFICATIONS permission request.
  // On older Android and on iOS, this call shows the system permission dialog.
  const { status: existingStatus } =
    await Notifications.getPermissionsAsync();

  let finalStatus = existingStatus;
  if (existingStatus !== 'granted') {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }

  if (finalStatus !== 'granted') {
    console.warn('[PushNotifications] Permission not granted by the user.');
    return { status: 'permission-denied' };
  }

  // Android requires a notification channel to be created before tokens are
  // useful. This is a no-op on iOS.
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('default', {
      name: 'UniAttend Notifications',
      importance: Notifications.AndroidImportance.MAX,
      vibrationPattern: [0, 250, 250, 250],
      lightColor: '#208AEF',
    });
  }

  let expoPushToken: string;
  try {
    const projectId =
      Constants?.expoConfig?.extra?.eas?.projectId ??
      Constants?.easConfig?.projectId;

    const tokenResponse = await Notifications.getExpoPushTokenAsync(
      projectId ? { projectId } : undefined,
    );
    expoPushToken = tokenResponse.data;
  } catch (error) {
    const reason =
      error instanceof Error ? error.message : 'Unknown error getting token';
    console.error('[PushNotifications] Failed to get Expo push token:', reason);
    return { status: 'error', reason };
  }

  const platform = resolvePlatform();
  const result = await coreApiClient.post<unknown>(deviceRegistrationPath, {
    expo_push_token: expoPushToken,
    platform,
  });

  if (result.status !== 'ok') {
    console.error(
      '[PushNotifications] Failed to register token with backend:',
      result.status,
    );
    return {
      status: 'error',
      reason: `Backend registration failed: ${result.status}`,
    };
  }

  // The token itself is a delivery credential: anyone holding it can push to
  // this device. Log that registration happened, never what was registered.
  console.info(
    '[PushNotifications] Device token registered successfully.',
    { platform },
  );

  return { status: 'registered' };
}

function resolvePlatform(): 'android' | 'ios' | 'web' {
  if (Platform.OS === 'android') return 'android';
  if (Platform.OS === 'ios') return 'ios';
  return 'web';
}

/**
 * Revoke the device push token on backend (e.g. during logout or token rotation).
 */
export async function revokePushNotifications(
  coreApiClient: CoreApiClient,
  expoPushToken: string,
): Promise<boolean> {
  try {
    const result = await coreApiClient.post<unknown>(
      `${deviceRegistrationPath}/revoke`,
      {
        expo_push_token: expoPushToken,
      },
    );
    return result.status === 'ok';
  } catch (err) {
    console.warn('[PushNotifications] Failed to revoke push token:', err);
    return false;
  }
}
