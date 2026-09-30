// Waiver reasons accepted by the core API for a session-wide geofence waiver.
export const GEOFENCE_WAIVER_REASONS = [
  { code: "GPS_UNAVAILABLE", label: "GPS unavailable" },
  { code: "GPS_INACCURATE", label: "GPS inaccurate" },
  { code: "WRONG_SESSION_LOCATION", label: "Wrong session location" },
  { code: "DEVICE_LOCATION_FAILURE", label: "Device location failure" },
  { code: "OTHER", label: "Other" },
] as const;

export type GeofenceWaiverReasonCode = (typeof GEOFENCE_WAIVER_REASONS)[number]["code"];

export function geofenceWaiverReasonLabel(code: string): string {
  return GEOFENCE_WAIVER_REASONS.find((reason) => reason.code === code)?.label ?? code;
}

export function isGeofenceWaiverReasonCode(value: string): value is GeofenceWaiverReasonCode {
  return GEOFENCE_WAIVER_REASONS.some((reason) => reason.code === value);
}
