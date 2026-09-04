-- Migration: 0003_add_checkin_state_and_qr_batch_evidence_rollback
-- Removes only what 0003 added. No pre-existing column, row or constraint
-- is affected. Any checked_in_at / qr_batch_id values written since 0003
-- was applied are lost, which is why this is a development-only escape hatch.

BEGIN;

DROP INDEX IF EXISTS attendance_verification.idx_qr_validation_attempts_batch;
DROP INDEX IF EXISTS attendance_session.idx_qr_token_batches_session;

ALTER TABLE attendance_verification.qr_validation_attempts
  DROP CONSTRAINT IF EXISTS "FK_qr_validation_attempts_qr_batch_id";

ALTER TABLE attendance_verification.qr_validation_attempts
  DROP COLUMN IF EXISTS qr_batch_id;

ALTER TABLE attendance_verification.verification_attempts
  DROP CONSTRAINT IF EXISTS ck_verification_attempts_checked_in_has_timestamp;

ALTER TABLE attendance_verification.verification_attempts
  DROP COLUMN IF EXISTS checked_in_at;

COMMIT;
