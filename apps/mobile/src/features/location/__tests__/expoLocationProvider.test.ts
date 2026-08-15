import { beforeEach, describe, expect, jest, test } from '@jest/globals';
import * as Location from 'expo-location';

import { ExpoLocationProvider } from '../services/expoLocationProvider';

jest.mock('expo-location', () => ({
  Accuracy: { High: 4 },
  requestForegroundPermissionsAsync: jest.fn(),
  hasServicesEnabledAsync: jest.fn(),
  getCurrentPositionAsync: jest.fn(),
}));

const requestPermission = jest.mocked(
  Location.requestForegroundPermissionsAsync,
);
const hasServicesEnabled = jest.mocked(Location.hasServicesEnabledAsync);
const getCurrentPosition = jest.mocked(Location.getCurrentPositionAsync);

function locationObject(
  overrides: Partial<Location.LocationObject> = {},
): Location.LocationObject {
  return {
    coords: {
      latitude: 6.795132,
      longitude: 79.900421,
      accuracy: 18.5,
      altitude: null,
      altitudeAccuracy: null,
      heading: null,
      speed: null,
    },
    timestamp: Date.parse('2026-08-13T05:30:14Z'),
    mocked: false,
    ...overrides,
  };
}

describe('ExpoLocationProvider', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    requestPermission.mockResolvedValue({ granted: true } as never);
    hasServicesEnabled.mockResolvedValue(true);
    getCurrentPosition.mockResolvedValue(locationObject());
  });

  test('returns permission denied without requesting a coordinate', async () => {
    requestPermission.mockResolvedValue({ granted: false } as never);

    await expect(
      new ExpoLocationProvider().captureFreshLocation(),
    ).resolves.toEqual({ status: 'permission_denied' });
    expect(hasServicesEnabled).not.toHaveBeenCalled();
    expect(getCurrentPosition).not.toHaveBeenCalled();
  });

  test('reports disabled location services without requesting a coordinate', async () => {
    hasServicesEnabled.mockResolvedValue(false);

    await expect(
      new ExpoLocationProvider().captureFreshLocation(),
    ).resolves.toEqual({ status: 'services_disabled' });
    expect(getCurrentPosition).not.toHaveBeenCalled();
  });

  test('captures a fresh high-accuracy reading and Android mocked flag', async () => {
    getCurrentPosition.mockResolvedValue(locationObject({ mocked: true }));

    await expect(
      new ExpoLocationProvider().captureFreshLocation(),
    ).resolves.toEqual({
      status: 'captured',
      reading: {
        latitude: 6.795132,
        longitude: 79.900421,
        accuracyM: 18.5,
        capturedAt: '2026-08-13T05:30:14.000Z',
        mocked: true,
      },
    });
    expect(getCurrentPosition).toHaveBeenCalledWith({
      accuracy: Location.Accuracy.High,
    });
  });

  test('preserves unavailable accuracy for a server retry decision', async () => {
    getCurrentPosition.mockResolvedValue(
      locationObject({
        coords: {
          ...locationObject().coords,
          accuracy: null,
        },
      }),
    );

    const result = await new ExpoLocationProvider().captureFreshLocation();

    expect(result).toEqual(
      expect.objectContaining({
        status: 'captured',
        reading: expect.objectContaining({ accuracyM: null }),
      }),
    );
  });

  test('reports unavailable when the native provider throws', async () => {
    getCurrentPosition.mockRejectedValue(new Error('provider unavailable'));

    await expect(
      new ExpoLocationProvider().captureFreshLocation(),
    ).resolves.toEqual({ status: 'unavailable' });
  });

  test('rejects invalid native coordinates without sending them onward', async () => {
    getCurrentPosition.mockResolvedValue(
      locationObject({
        coords: {
          ...locationObject().coords,
          latitude: 91,
        },
      }),
    );

    await expect(
      new ExpoLocationProvider().captureFreshLocation(),
    ).resolves.toEqual({ status: 'unavailable' });
  });
});
