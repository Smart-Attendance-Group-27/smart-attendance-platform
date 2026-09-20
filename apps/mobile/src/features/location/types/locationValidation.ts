import type { InitialCheckIn } from '../../attendance/types/myAttendance';

export type LocationValidationResult =
  | { status: 'inside_geofence'; initialCheckIn?: InitialCheckIn | null }
  | { status: 'outside_geofence' }
  | { status: 'permission_denied' }
  | { status: 'services_disabled' }
  | { status: 'poor_accuracy' }
  | { status: 'retry_required' }
  | { status: 'stale_location' }
  | { status: 'unavailable' }
  | { status: 'mock_location_detected' }
  | { status: 'session_unavailable' }
  | { status: 'already_checked_in' }
  | { status: 'attempt_limit_reached' }
  | { status: 'unauthenticated' }
  | { status: 'forbidden' }
  | { status: 'invalid_request' }
  | { status: 'network_error' }
  | { status: 'server_error' };
