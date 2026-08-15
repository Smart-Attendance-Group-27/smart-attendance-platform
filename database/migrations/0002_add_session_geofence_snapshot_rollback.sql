-- Rollback for: 0002_add_session_geofence_snapshot
--
-- This removes only the frozen snapshot fields and their validation checks.
-- Existing session rows, verification attempts, and attendance records remain.

BEGIN;

ALTER TABLE attendance_session.session_geofences
  DROP CONSTRAINT IF EXISTS ck_session_geofences_snapshot_all_or_none,
  DROP CONSTRAINT IF EXISTS ck_session_geofences_centre_latitude_range,
  DROP CONSTRAINT IF EXISTS ck_session_geofences_centre_longitude_range,
  DROP CONSTRAINT IF EXISTS ck_session_geofences_radius_positive,
  DROP CONSTRAINT IF EXISTS ck_session_geofences_accuracy_buffer_nonnegative,
  DROP CONSTRAINT IF EXISTS ck_session_geofences_maximum_accuracy_nonnegative;

ALTER TABLE attendance_session.session_geofences
  DROP COLUMN IF EXISTS centre_latitude,
  DROP COLUMN IF EXISTS centre_longitude,
  DROP COLUMN IF EXISTS radius_m;

COMMIT;
