import { describe, expect, jest, test } from '@jest/globals';
import { waitFor } from '@testing-library/react-native';
import type { DevicePushToken } from 'expo-notifications';
import type { CoreApiClient } from '../../../services/api/coreApiClient';
import {
  listenForPushTokenChanges,
  registerForPushNotifications,
  resetPushRegistrationStatus,
  type PushRegistrationOptions,
} from '../services/pushNotificationService';

describe('push token registration', () => {
  test('registers a rotated native token as a new Expo token and revokes the old one', async () => {
    resetPushRegistrationStatus();
    const tokens = ['ExpoPushToken[old]', 'ExpoPushToken[new]'];
    let listener: ((token: DevicePushToken) => void) | undefined;
    const remove = jest.fn();
    const notifications = {
      setNotificationChannelAsync: jest.fn(async () => undefined),
      getPermissionsAsync: jest.fn(async () => ({ status: 'granted' })),
      requestPermissionsAsync: jest.fn(async () => ({ status: 'granted' })),
      getExpoPushTokenAsync: jest.fn(async () => ({ data: tokens.shift() })),
      addPushTokenListener: jest.fn((callback: (token: DevicePushToken) => void) => {
        listener = callback;
        return { remove };
      }),
    } as unknown as NonNullable<PushRegistrationOptions['notifications']>;
    const posts: { path: string; body: { expo_push_token: string } }[] = [];
    const client = {
      post: jest.fn(async (path: string, body: { expo_push_token: string }) => {
        posts.push({ path, body });
        return { status: 'ok', data: {} };
      }),
    } as unknown as CoreApiClient;

    const result = await registerForPushNotifications(client, {
      notifications, isDevice: true, platform: 'android', projectId: 'test-project',
    });
    expect(result.status).toBe('registered');
    expect(notifications.setNotificationChannelAsync).toHaveBeenCalled();
    const stop = listenForPushTokenChanges(client, notifications, 'test-project');
    const nativeToken: DevicePushToken = { type: 'android', data: 'new-native-fcm-token' };
    listener?.(nativeToken);
    await waitFor(() => expect(posts).toHaveLength(3));

    expect(notifications.getExpoPushTokenAsync).toHaveBeenLastCalledWith({
      projectId: 'test-project',
      devicePushToken: nativeToken,
    });

    expect(posts.map(({ body }) => body.expo_push_token)).toEqual([
      'ExpoPushToken[old]', 'ExpoPushToken[new]', 'ExpoPushToken[old]',
    ]);
    expect(posts[2].path).toContain('/revoke');
    stop();
    expect(remove).toHaveBeenCalled();
  });
});
