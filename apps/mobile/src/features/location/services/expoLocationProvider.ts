import * as Location from 'expo-location';

import type { LocationProvider } from './locationProvider';
import type {
  FreshLocationReading,
  FreshLocationResult,
} from '../types/locationReading';

export class ExpoLocationProvider implements LocationProvider {
  async captureFreshLocation(): Promise<FreshLocationResult> {
    try {
      const permission = await Location.requestForegroundPermissionsAsync();

      if (!permission.granted) {
        return { status: 'permission_denied' };
      }

      if (!(await Location.hasServicesEnabledAsync())) {
        return { status: 'services_disabled' };
      }

      const location = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.High,
      });
      const reading = toFreshLocationReading(location);

      return reading
        ? { status: 'captured', reading }
        : { status: 'unavailable' };
    } catch {
      return { status: 'unavailable' };
    }
  }
}

function toFreshLocationReading(
  location: Location.LocationObject,
): FreshLocationReading | null {
  const { accuracy, latitude, longitude } = location.coords;

  if (
    !Number.isFinite(latitude) ||
    latitude < -90 ||
    latitude > 90 ||
    !Number.isFinite(longitude) ||
    longitude < -180 ||
    longitude > 180 ||
    !Number.isFinite(location.timestamp) ||
    (accuracy !== null && (!Number.isFinite(accuracy) || accuracy < 0))
  ) {
    return null;
  }

  const capturedAt = new Date(location.timestamp);
  if (Number.isNaN(capturedAt.getTime())) {
    return null;
  }

  return {
    latitude,
    longitude,
    accuracyM: accuracy,
    capturedAt: capturedAt.toISOString(),
    mocked: location.mocked === true,
  };
}
