-- Migration: 20260920_01_attendance_lifecycle_columns
-- Purpose:   Add the columns the attendance lifecycle needs, without changing
--            any existing behaviour.
--
-- This is the first migration of the new attendance model. It is deliberately
-- additive only: every column is nullable, every constraint added here is
-- satisfied by existing rows, and nothing is dropped or renamed. The code that
-- is running today ignores these columns, so this migration can be applied
-- before the features that use them are merged, which is what lets all four
-- workstreams develop in parallel.
--
-- What it adds:
--   1. attendance_verification.verification_attempts
--      checked_in_at / initial_check_in_status - the stored initial check-in,
--      which is an intermediate state and never a final attendance result.
--   2. attendance_verification.qr_validation_attempts
--      qr_batch_id - so a scan can be attributed to the QR batch it belongs to.
--      Dynamic QR batches never create a qr_tokens row, so today their attempts
--      cannot be attributed at all; from here on the column is written directly.
--      Existing static rows are backfilled through qr_tokens; historical dynamic
--      rows stay NULL and are ignored by the evidence queries.
--   3. attendance_session.qr_token_batches
--      voided_at / voided_by / void_reason - so a batch activated by mistake can
--      later be excluded from attendance requirements without deleting history.
--
-- The state backfill and the CHECK constraints on status values arrive in the
-- next migration, together with the code that depends on them.
--
-- Apply with the Supabase SQL editor or psql. Never put database credentials
-- into this file or into the command used to run it.

BEGIN;

-- 1. Initial check-in state ---------------------------------------------------

ALTER TABLE attendance_verification.verification_attempts
  ADD COLUMN IF NOT EXISTS checked_in_at timestamp with time zone,
  ADD COLUMN IF NOT EXISTS initial_check_in_status character varying(20);

COMMENT ON COLUMN attendance_verification.verification_attempts.checked_in_at IS
  'When the last required initial verification step passed. NULL until the student is checked in.';
COMMENT ON COLUMN attendance_verification.verification_attempts.initial_check_in_status IS
  'checked_in or late_checked_in. An intermediate state; final attendance lives in attendance_records.';

-- Finalization, the lecturer roster and the student active-session list all
-- filter a session's attempts by status.
CREATE INDEX IF NOT EXISTS ix_verification_attempts_session_status
  ON attendance_verification.verification_attempts (session_id, status);

-- 2. QR evidence attribution ---------------------------------------------------

ALTER TABLE attendance_verification.qr_validation_attempts
  ADD COLUMN IF NOT EXISTS qr_batch_id uuid;

COMMENT ON COLUMN attendance_verification.qr_validation_attempts.qr_batch_id IS
  'The QR batch this scan belongs to. NULL only for historical dynamic-QR rows, which cannot be attributed.';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'fk_qr_validation_attempts_qr_batch'
      AND conrelid = 'attendance_verification.qr_validation_attempts'::regclass
  ) THEN
    ALTER TABLE attendance_verification.qr_validation_attempts
      ADD CONSTRAINT fk_qr_validation_attempts_qr_batch
      FOREIGN KEY (qr_batch_id)
      REFERENCES attendance_session.qr_token_batches (id);
  END IF;
END
$$;

-- Static batches keep exactly one qr_tokens row, so their existing attempts can
-- be attributed. Re-running this is harmless: it only fills NULLs.
UPDATE attendance_verification.qr_validation_attempts AS attempt
SET qr_batch_id = token.qr_batch_id
FROM attendance_session.qr_tokens AS token
WHERE token.id = attempt.qr_token_id
  AND attempt.qr_batch_id IS NULL;

-- "Has this student passed this batch?" is the single question finalization and
-- the progress endpoints ask, so the index covers exactly that lookup.
-- It is deliberately NOT unique: historical data may already hold more than one
-- accepted row for the same batch, and the service prevents new duplicates.
CREATE INDEX IF NOT EXISTS ix_qr_attempts_accepted_batch
  ON attendance_verification.qr_validation_attempts (verification_attempt_id, qr_batch_id)
  WHERE validation_status = 'accepted';

-- Counting participation per batch for the lecturer view.
CREATE INDEX IF NOT EXISTS ix_qr_attempts_batch
  ON attendance_verification.qr_validation_attempts (qr_batch_id);

-- 3. Voidable QR batches --------------------------------------------------------

ALTER TABLE attendance_session.qr_token_batches
  ADD COLUMN IF NOT EXISTS voided_at timestamp with time zone,
  ADD COLUMN IF NOT EXISTS voided_by uuid,
  ADD COLUMN IF NOT EXISTS void_reason text;

COMMENT ON COLUMN attendance_session.qr_token_batches.voided_at IS
  'Set when a lecturer voids a batch created by mistake. Voided batches are excluded from attendance requirements.';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'fk_qr_token_batches_voided_by'
      AND conrelid = 'attendance_session.qr_token_batches'::regclass
  ) THEN
    ALTER TABLE attendance_session.qr_token_batches
      ADD CONSTRAINT fk_qr_token_batches_voided_by
      FOREIGN KEY (voided_by)
      REFERENCES identity.users (id);
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'ck_qr_token_batches_void_consistency'
      AND conrelid = 'attendance_session.qr_token_batches'::regclass
  ) THEN
    -- A void is always recorded in full: when, by whom and why.
    ALTER TABLE attendance_session.qr_token_batches
      ADD CONSTRAINT ck_qr_token_batches_void_consistency
      CHECK (
        (voided_at IS NULL AND voided_by IS NULL AND void_reason IS NULL)
        OR
        (voided_at IS NOT NULL AND voided_by IS NOT NULL AND void_reason IS NOT NULL)
      );
  END IF;
END
$$;

-- "Which batches of this session were activated after the student checked in?"
CREATE INDEX IF NOT EXISTS ix_qr_token_batches_session_activated
  ON attendance_session.qr_token_batches (session_id, activated_at);

COMMIT;
