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
import { setPushRegistrationStatus } from './pushRegistrationStatus';

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
  | { readonly status: 'unsupported-platform' }
  | { readonly status: 'error'; readonly reason: string };

type PushNotificationsApi = Pick<typeof Notifications,
  'setNotificationChannelAsync' | 'getPermissionsAsync' |
  'requestPermissionsAsync' | 'getExpoPushTokenAsync' | 'addPushTokenListener'>;

export type PushRegistrationOptions = {
  notifications?: PushNotificationsApi;
  isDevice?: boolean;
  platform?: string;
  projectId?: string;
};

let lastRegisteredToken: string | undefined;

export function resetPushRegistrationStatus(): void {
  lastRegisteredToken = undefined;
  setPushRegistrationStatus('checking');
}

/**
 * Request permission, obtain an Expo push token, and register it with the
 * backend.  Safe to call on every app launch — the backend upserts the token.
 */
export async function registerForPushNotifications(
  coreApiClient: CoreApiClient,
  options: PushRegistrationOptions = {},
): Promise<PushRegistrationResult> {
  const notificationApi = options.notifications ?? Notifications;
  setPushRegistrationStatus('checking');
  const finish = (result: PushRegistrationResult): PushRegistrationResult => {
    setPushRegistrationStatus(result.status);
    return result;
  };
  if ((options.platform ?? Platform.OS) !== 'android') {
    return finish({ status: 'unsupported-platform' });
  }
  // Expo push tokens are only issued for physical devices.
  if (!(options.isDevice ?? Device.isDevice)) {
    console.warn(
      '[PushNotifications] Push notifications are not available on the emulator.',
    );
    return finish({ status: 'not-a-physical-device' });
  }

  // Android 13 needs a channel before its notification permission dialog.
  try {
    await notificationApi.setNotificationChannelAsync('default', {
      name: 'UniAttend Notifications',
      importance: Notifications.AndroidImportance.MAX,
      vibrationPattern: [0, 250, 250, 250],
      lightColor: '#208AEF',
    });

    const { status: existingStatus } = await notificationApi.getPermissionsAsync();
    let finalStatus = existingStatus;
    if (existingStatus !== 'granted') {
      const response = await notificationApi.requestPermissionsAsync();
      finalStatus = response.status;
    }
    if (finalStatus !== 'granted') {
      return finish({ status: 'permission-denied' });
    }
  } catch {
    return finish({ status: 'error', reason: 'Could not check notification permission.' });
  }
  return finish(await registerCurrentToken(
    coreApiClient, notificationApi, options.projectId ?? resolveProjectId()?.projectId,
  ));
}

async function registerCurrentToken(
  coreApiClient: CoreApiClient,
  notificationApi: PushNotificationsApi,
  projectId: string | undefined,
): Promise<PushRegistrationResult> {
  try {
    if (!projectId) return { status: 'error', reason: 'EAS project ID is missing.' };
    const expoPushToken = (await notificationApi.getExpoPushTokenAsync({ projectId })).data;
    const result = await coreApiClient.post<unknown>(deviceRegistrationPath, {
      expo_push_token: expoPushToken,
      platform: 'android',
    });
    if (result.status !== 'ok') {
      return { status: 'error', reason: `Backend registration failed: ${result.status}` };
    }
    const previousToken = lastRegisteredToken;
    lastRegisteredToken = expoPushToken;
    if (previousToken && previousToken !== expoPushToken) {
      await revokePushNotifications(coreApiClient, previousToken);
    }
    return { status: 'registered' };
  } catch {
    return { status: 'error', reason: 'Could not obtain an Expo push token.' };
  }
}

export function listenForPushTokenChanges(
  coreApiClient: CoreApiClient,
  notificationApi: PushNotificationsApi = Notifications,
  projectId: string | undefined = resolveProjectId()?.projectId,
): () => void {
  const subscription = notificationApi.addPushTokenListener(() => {
    // The listener supplies a native FCM token. Re-register its current Expo
    // token because the Core API stores Expo tokens, never native tokens.
    void registerCurrentToken(coreApiClient, notificationApi, projectId).then((result) => {
      setPushRegistrationStatus(result.status);
    });
  });
  return () => subscription.remove();
}

/**
 * Revoke the device push token on backend (e.g. during logout or token rotation).
 */
export async function revokePushNotifications(
  coreApiClient: CoreApiClient,
  expoPushToken?: string,
): Promise<boolean> {
  try {
    if (!Device.isDevice && !expoPushToken && !lastRegisteredToken) {
      return false;
    }
    const token = expoPushToken ?? lastRegisteredToken ?? (
      await Notifications.getExpoPushTokenAsync(resolveProjectId())
    ).data;
    const result = await coreApiClient.post<unknown>(
      `${deviceRegistrationPath}/revoke`,
      {
        expo_push_token: token,
      },
    );
    if (result.status === 'ok' && token === lastRegisteredToken) {
      lastRegisteredToken = undefined;
    }
    return result.status === 'ok';
  } catch {
    console.warn('[PushNotifications] Failed to revoke push token.');
    return false;
  }
}

function resolveProjectId(): { projectId: string } | undefined {
  const projectId =
    Constants?.expoConfig?.extra?.eas?.projectId ?? Constants?.easConfig?.projectId;
  return projectId ? { projectId } : undefined;
}
