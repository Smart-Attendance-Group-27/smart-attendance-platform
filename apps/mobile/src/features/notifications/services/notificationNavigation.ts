export type NotificationDestination =
  | `/(student)/attendance/${string}/progress`
  | '/(student)/(tabs)/notifications';

export function destinationForNotificationData(
  data: Record<string, unknown> | undefined,
): NotificationDestination {
  const entityType = readString(data?.relatedEntityType)?.toUpperCase();
  const entityId = readString(data?.relatedEntityId);

  if (entityType === 'ATTENDANCE_SESSION' && entityId) {
    return `/(student)/attendance/${entityId}/progress`;
  }
  return '/(student)/(tabs)/notifications';
}

export function destinationForNotificationResponse(
  response: NotificationResponse,
): NotificationDestination {
  return destinationForNotificationData(
    response.notification.request.content.data as Record<string, unknown>,
  );
}

type NotificationResponse = {
  notification: { request: { content: { data?: Record<string, unknown> } } };
};

type NotificationApi = {
  addNotificationResponseReceivedListener(
    listener: (response: NotificationResponse) => void,
  ): { remove(): void };
  getLastNotificationResponseAsync(): Promise<NotificationResponse | null>;
  clearLastNotificationResponseAsync(): Promise<void>;
};

export function installNotificationNavigation(
  navigate: (destination: NotificationDestination) => void,
  api: NotificationApi,
): () => void {
  let active = true;
  const open = (response: NotificationResponse) => {
    navigate(destinationForNotificationResponse(response));
  };
  const subscription = api.addNotificationResponseReceivedListener(open);
  void api.getLastNotificationResponseAsync().then((response) => {
    if (active && response) {
      open(response);
      void api.clearLastNotificationResponseAsync();
    }
  });
  return () => {
    active = false;
    subscription.remove();
  };
}

function readString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value : undefined;
}
