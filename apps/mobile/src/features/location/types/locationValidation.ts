export type LocationValidationResult =
  | { status: 'inside_geofence' }
  | { status: 'outside_geofence' }
  | { status: 'permission_denied' }
  | { status: 'poor_accuracy' }
  | { status: 'stale_location' }
  | { status: 'unavailable' };
