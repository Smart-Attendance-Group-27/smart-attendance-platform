-- Migration: 0003_add_checkin_state_and_qr_batch_evidence
-- Purpose:   Support two separate attendance decisions.
--
--   1. A provisional CHECKED_IN state produced by geofence + face at the
--      start of the lecture, with a reliable timestamp for when it happened.
--   2. Per-QR-window student evidence, so a lecturer may run zero, one or
--      many QR verification windows and each is judged independently.
--
-- attendance_verification.attendance_records is deliberately NOT touched:
-- it stays the FINAL academic result (present/late/absent) and is written
-- only when the session is finalized.
--
-- This migration is additive and reversible:
--   * no column is dropped or renamed
--   * no row is deleted or rewritten
--   * requires_qr and every other existing column are left untouched
--
-- Apply with the Supabase SQL editor or psql. Never put database
-- credentials into this file or into the command used to run it.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Provisional check-in timestamp
-- ---------------------------------------------------------------------------
-- started_at already records when the student BEGAN verifying (the geofence
-- call). checked_in_at records when they FINISHED initial check-in (geofence
-- passed AND face passed). The two differ by however long the face step took,
-- and QR applicability is measured from the finish, not the start, so the
-- distinction has to be stored rather than inferred.
--
-- NULL means "this student has not completed initial check-in".

ALTER TABLE attendance_verification.verification_attempts
  ADD COLUMN IF NOT EXISTS checked_in_at timestamp with time zone;

COMMENT ON COLUMN attendance_verification.verification_attempts.checked_in_at IS
  'When initial check-in completed (geofence passed AND face passed). NULL '
  'until then. Used as the reference point for deciding which lecturer QR '
  'windows apply to this student.';

-- Integrity guard: a row claiming the provisional CHECKED_IN state must carry
-- the timestamp the QR applicability rule depends on. Rows with any other
-- status, including NULL status, are unaffected (a CHECK only fails on FALSE).
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'ck_verification_attempts_checked_in_has_timestamp'
      AND conrelid = 'attendance_verification.verification_attempts'::regclass
  ) THEN
    ALTER TABLE attendance_verification.verification_attempts
      ADD CONSTRAINT ck_verification_attempts_checked_in_has_timestamp
      CHECK (status <> 'checked_in' OR checked_in_at IS NOT NULL);
  END IF;
END
$$;

-- ---------------------------------------------------------------------------
-- 2. Tie each QR scan to the lecturer QR window it was made against
-- ---------------------------------------------------------------------------
-- qr_token_id only resolves to a batch for STATIC QR. Dynamic QR persists no
-- qr_tokens row at all (values are recomputed from HMAC), so every dynamic
-- attempt is currently written with qr_token_id = NULL and cannot be traced
-- back to a window. That makes "did this student pass QR #2?" unanswerable.
-- qr_batch_id records it directly and works for both modes.

ALTER TABLE attendance_verification.qr_validation_attempts
  ADD COLUMN IF NOT EXISTS qr_batch_id uuid;

-- Backfill the static-mode rows that CAN be traced. A no-op on a database
-- with no historical QR attempts (production has none).
UPDATE attendance_verification.qr_validation_attempts AS attempt
SET qr_batch_id = token.qr_batch_id
FROM attendance_session.qr_tokens AS token
WHERE token.id = attempt.qr_token_id
  AND attempt.qr_batch_id IS NULL;

-- Fail with a readable message rather than a raw constraint violation if a
-- local database holds untraceable legacy dynamic-QR rows.
DO $$
DECLARE
  untraceable_rows bigint;
BEGIN
  SELECT count(*) INTO untraceable_rows
  FROM attendance_verification.qr_validation_attempts
  WHERE qr_batch_id IS NULL;

  IF untraceable_rows > 0 THEN
    RAISE EXCEPTION
      'Cannot set qr_batch_id NOT NULL: % qr_validation_attempts row(s) '
      'predate this column and have no resolvable QR batch. Delete or '
      'manually attribute those development rows, then re-run.',
      untraceable_rows;
  END IF;
END
$$;

ALTER TABLE attendance_verification.qr_validation_attempts
  ALTER COLUMN qr_batch_id SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'FK_qr_validation_attempts_qr_batch_id'
      AND conrelid = 'attendance_verification.qr_validation_attempts'::regclass
  ) THEN
    ALTER TABLE attendance_verification.qr_validation_attempts
      ADD CONSTRAINT "FK_qr_validation_attempts_qr_batch_id"
      FOREIGN KEY (qr_batch_id)
      REFERENCES attendance_session.qr_token_batches(id);
  END IF;
END
$$;

COMMENT ON COLUMN attendance_verification.qr_validation_attempts.qr_batch_id IS
  'The lecturer-created QR verification window this scan was made against. '
  'Set for both static and dynamic QR. Finalization counts DISTINCT '
  'qr_batch_id values with validation_status = ''accepted'', so a student''s '
  'repeated retries against one window count once.';

-- ---------------------------------------------------------------------------
-- 3. Indexes for the finalization queries
-- ---------------------------------------------------------------------------
-- Finalization asks two questions per session: which QR windows exist, and
-- which distinct windows did each student satisfy. Neither had an index.
-- (verification_attempts is already covered by
--  uq_verification_attempts_session_student, whose leading column is session_id.)

CREATE INDEX IF NOT EXISTS idx_qr_token_batches_session
  ON attendance_session.qr_token_batches (session_id);

CREATE INDEX IF NOT EXISTS idx_qr_validation_attempts_batch
  ON attendance_verification.qr_validation_attempts
     (verification_attempt_id, qr_batch_id, validation_status);

COMMIT;
