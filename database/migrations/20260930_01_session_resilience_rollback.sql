-- Rollback: 20260930_01_session_resilience
--
-- Refuses to run while any attendance record is 'left_early', because the old
-- status constraint would reject it. Decide what those records should be
-- first. Dropping the overrides table removes the record of every geofence
-- waiver; the audit log entries written with each waiver are kept.

BEGIN;

DO $$
DECLARE
  left_early_count bigint;
BEGIN
  SELECT count(*)
  INTO left_early_count
  FROM attendance_verification.attendance_records
  WHERE attendance_status = 'left_early';

  IF left_early_count > 0 THEN
    RAISE EXCEPTION
      '% attendance record(s) are left_early. Change them before rolling back '
      '20260930_01.', left_early_count;
  END IF;
END
$$;

ALTER TABLE attendance_verification.attendance_records
  DROP CONSTRAINT IF EXISTS ck_attendance_records_status;

ALTER TABLE attendance_verification.attendance_records
  ADD CONSTRAINT ck_attendance_records_status
  CHECK (attendance_status IN ('present', 'late', 'absent'));

DROP INDEX IF EXISTS attendance_session.idx_sessions_open_by_scheduled_end;

ALTER TABLE attendance_session.sessions
  DROP COLUMN IF EXISTS closed_automatically;

DROP TABLE IF EXISTS attendance_session.session_verification_overrides;

COMMIT;
