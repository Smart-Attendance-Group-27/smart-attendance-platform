export const DEFAULT_APP_TIME_ZONE = 'Asia/Colombo';

function isValidTimeZone(timeZone: string): boolean {
  try {
    new Intl.DateTimeFormat('en-GB', { timeZone });
    return true;
  } catch {
    return false;
  }
}

// Session, lecture and check-in times belong to the institution, so they are
// shown in its timezone whatever the device is set to. (Notification arrival
// times and the greeting deliberately follow the device instead.)
export function getAppTimeZone(): string {
  // Expo only inlines public variables that are read as a direct property.
  const configured = process.env.EXPO_PUBLIC_APP_TIMEZONE?.trim();
  return configured && isValidTimeZone(configured) ? configured : DEFAULT_APP_TIME_ZONE;
}
