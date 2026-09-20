-- Rollback: 20260920_02_attendance_check_in_state
--
-- Puts the status vocabulary back the way the previous release understood it,
-- so the old code can serve traffic again. Run this before redeploying that
-- code, not after.
--
-- What is lost:
--   * The distinction between an attempt that checked in under the new code and
--     one that was backfilled: both become 'completed' again.
--   * Nothing else. checked_in_at and initial_check_in_status keep their values
--     and are simply ignored by the old code. Rolling back migration 01 is what
--     removes them, and that is a separate, later step.
--
-- 'in_progress' and 'failed' are untouched: both predate this migration.

BEGIN;

ALTER TABLE attendance_verification.verification_attempts
  DROP CONSTRAINT IF EXISTS ck_verification_attempts_check_in_pairing;

ALTER TABLE attendance_verification.verification_attempts
  DROP CONSTRAINT IF EXISTS ck_verification_attempts_initial_check_in_status;

ALTER TABLE attendance_verification.verification_attempts
  DROP CONSTRAINT IF EXISTS ck_verification_attempts_status;

UPDATE attendance_verification.verification_attempts
SET status = 'completed'
WHERE status = 'checked_in';

COMMIT;
