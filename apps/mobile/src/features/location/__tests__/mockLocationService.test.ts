import { describe, expect, test } from '@jest/globals';

import type { LocationService } from '../services/locationService';
import { MockLocationService } from '../services/mockLocationService';
import type { LocationValidationResult } from '../types/locationValidation';

const locationOutcomes: readonly LocationValidationResult[] = [
  { status: 'inside_geofence' },
  { status: 'outside_geofence' },
  { status: 'permission_denied' },
  { status: 'poor_accuracy' },
  { status: 'stale_location' },
  { status: 'unavailable' },
];

describe('MockLocationService', () => {
  test.each(locationOutcomes)(
    'returns the configured $status outcome',
    async (configuredResult) => {
      const service = new MockLocationService({
        result: configuredResult,
      });

      await expect(
        service.validateLocation('attendance-session-active'),
      ).resolves.toEqual(configuredResult);
    },
  );

  test('implements the LocationService contract', async () => {
    const service: LocationService = new MockLocationService({
      result: { status: 'inside_geofence' },
    });

    const result: Promise<LocationValidationResult> =
      service.validateLocation('attendance-session-active');

    await expect(result).resolves.toEqual({
      status: 'inside_geofence',
    });
  });

  test('returns the same configured outcome for repeated validations', async () => {
    const configuredResult: LocationValidationResult = {
      status: 'outside_geofence',
    };
    const service = new MockLocationService({
      result: configuredResult,
    });

    await expect(
      service.validateLocation('attendance-session-one'),
    ).resolves.toEqual(configuredResult);
    await expect(
      service.validateLocation('attendance-session-two'),
    ).resolves.toEqual(configuredResult);
  });
});
