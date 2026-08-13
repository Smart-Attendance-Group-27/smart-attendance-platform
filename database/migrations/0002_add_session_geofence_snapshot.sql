-- Migration: 0002_add_session_geofence_snapshot
-- Purpose:   Freeze the geofence centre and radius used by each attendance
--            session so later classroom edits cannot change an active or
--            historical validation boundary.
--
-- Existing session geofences are backfilled only when their timetable resolves
-- to a classroom with a complete, valid geofence. Rows that cannot be resolved
-- remain unconfigured and can be handled explicitly by the application.

BEGIN;

ALTER TABLE attendance_session.session_geofences
  ADD COLUMN IF NOT EXISTS centre_latitude NUMERIC,
  ADD COLUMN IF NOT EXISTS centre_longitude NUMERIC,
  ADD COLUMN IF NOT EXISTS radius_m NUMERIC;

UPDATE attendance_session.session_geofences AS session_geofence
SET centre_latitude = classroom.latitude,
    centre_longitude = classroom.longitude,
    radius_m = classroom.default_geofence_radius_m
FROM attendance_session.sessions AS attendance_session
LEFT JOIN academic.timetable_entries AS timetable_entry
  ON timetable_entry.id = attendance_session.timetable_entry_id
LEFT JOIN academic.timetable_exceptions AS timetable_exception
  ON timetable_exception.id = attendance_session.timetable_exception_id
JOIN academic.classrooms AS classroom
  ON classroom.id = COALESCE(
    timetable_exception.new_classroom_id,
    timetable_entry.classroom_id
  )
WHERE session_geofence.session_id = attendance_session.id
  AND session_geofence.centre_latitude IS NULL
  AND session_geofence.centre_longitude IS NULL
  AND session_geofence.radius_m IS NULL
  AND classroom.latitude BETWEEN -90 AND 90
  AND classroom.longitude BETWEEN -180 AND 180
  AND classroom.default_geofence_radius_m > 0;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'ck_session_geofences_snapshot_all_or_none'
      AND conrelid = 'attendance_session.session_geofences'::regclass
  ) THEN
    ALTER TABLE attendance_session.session_geofences
      ADD CONSTRAINT ck_session_geofences_snapshot_all_or_none
      CHECK (
        (
          centre_latitude IS NULL
          AND centre_longitude IS NULL
          AND radius_m IS NULL
        )
        OR
        (
          centre_latitude IS NOT NULL
          AND centre_longitude IS NOT NULL
          AND radius_m IS NOT NULL
        )
      );
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'ck_session_geofences_centre_latitude_range'
      AND conrelid = 'attendance_session.session_geofences'::regclass
  ) THEN
    ALTER TABLE attendance_session.session_geofences
      ADD CONSTRAINT ck_session_geofences_centre_latitude_range
      CHECK (centre_latitude IS NULL OR centre_latitude BETWEEN -90 AND 90);
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'ck_session_geofences_centre_longitude_range'
      AND conrelid = 'attendance_session.session_geofences'::regclass
  ) THEN
    ALTER TABLE attendance_session.session_geofences
      ADD CONSTRAINT ck_session_geofences_centre_longitude_range
      CHECK (centre_longitude IS NULL OR centre_longitude BETWEEN -180 AND 180);
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'ck_session_geofences_radius_positive'
      AND conrelid = 'attendance_session.session_geofences'::regclass
  ) THEN
    ALTER TABLE attendance_session.session_geofences
      ADD CONSTRAINT ck_session_geofences_radius_positive
      CHECK (radius_m IS NULL OR radius_m > 0);
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'ck_session_geofences_accuracy_buffer_nonnegative'
      AND conrelid = 'attendance_session.session_geofences'::regclass
  ) THEN
    ALTER TABLE attendance_session.session_geofences
      ADD CONSTRAINT ck_session_geofences_accuracy_buffer_nonnegative
      CHECK (accuracy_buffer_m IS NULL OR accuracy_buffer_m >= 0);
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'ck_session_geofences_maximum_accuracy_nonnegative'
      AND conrelid = 'attendance_session.session_geofences'::regclass
  ) THEN
    ALTER TABLE attendance_session.session_geofences
      ADD CONSTRAINT ck_session_geofences_maximum_accuracy_nonnegative
      CHECK (
        maximum_allowed_accuracy_m IS NULL
        OR maximum_allowed_accuracy_m >= 0
      );
  END IF;
END
$$;

COMMENT ON COLUMN attendance_session.session_geofences.centre_latitude IS
  'Frozen geofence centre latitude copied for this attendance session.';
COMMENT ON COLUMN attendance_session.session_geofences.centre_longitude IS
  'Frozen geofence centre longitude copied for this attendance session.';
COMMENT ON COLUMN attendance_session.session_geofences.radius_m IS
  'Frozen geofence radius in metres copied for this attendance session.';

COMMIT;
