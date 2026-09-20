-- Rollback: 20260920_01_attendance_lifecycle_columns
--
-- Removes everything that migration added, in reverse order. Because the
-- migration is additive and the code running today ignores these columns, the
-- rollback is safe while no lifecycle feature is deployed.
--
-- It does drop columns, so anything already written to them is lost:
--   * initial check-in state recorded by CheckInService
--   * QR batch attribution (both backfilled and newly written)
--   * QR batch void records
-- Only run it while those features are not in use, and never as a way to
-- "undo" attendance data.

BEGIN;

-- 3. Voidable QR batches --------------------------------------------------------

DROP INDEX IF EXISTS attendance_session.ix_qr_token_batches_session_activated;

ALTER TABLE attendance_session.qr_token_batches
  DROP CONSTRAINT IF EXISTS ck_qr_token_batches_void_consistency;

ALTER TABLE attendance_session.qr_token_batches
  DROP CONSTRAINT IF EXISTS fk_qr_token_batches_voided_by;

ALTER TABLE attendance_session.qr_token_batches
  DROP COLUMN IF EXISTS void_reason,
  DROP COLUMN IF EXISTS voided_by,
  DROP COLUMN IF EXISTS voided_at;

-- 2. QR evidence attribution ---------------------------------------------------

DROP INDEX IF EXISTS attendance_verification.ix_qr_attempts_batch;
DROP INDEX IF EXISTS attendance_verification.ix_qr_attempts_accepted_batch;

ALTER TABLE attendance_verification.qr_validation_attempts
  DROP CONSTRAINT IF EXISTS fk_qr_validation_attempts_qr_batch;

ALTER TABLE attendance_verification.qr_validation_attempts
  DROP COLUMN IF EXISTS qr_batch_id;

-- 1. Initial check-in state ---------------------------------------------------

DROP INDEX IF EXISTS attendance_verification.ix_verification_attempts_session_status;

ALTER TABLE attendance_verification.verification_attempts
  DROP COLUMN IF EXISTS initial_check_in_status,
  DROP COLUMN IF EXISTS checked_in_at;

COMMIT;
