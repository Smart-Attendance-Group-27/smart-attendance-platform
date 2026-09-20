-- Migration: 20260920_02_attendance_check_in_state
-- Purpose:   Fill in the initial check-in state for attempts that already
--            completed, move the status vocabulary to its frozen form, and
--            constrain both so nothing can write a value outside it.
--
-- Depends on 20260920_01_attendance_lifecycle_columns, which added the columns
-- this one fills. Apply that first.
--
-- IMPORTANT - APPLY THIS WITH THE MATCHING CODE, NOT BEFORE IT.
-- Unlike migration 01 this is not purely additive. It renames the stored status
-- value 'completed' to 'checked_in' and then forbids 'completed' outright. The
-- code that writes 'completed' is replaced in the same pull request as this
-- file. Applying this while the previous release is still serving traffic would
-- make every check-in fail the CHECK constraint.
--
-- What it does:
--   1. Refuses to run if verification_attempts holds a status this migration
--      does not know about, naming the values it found. Better a clear failure
--      than a half-migrated table.
--   2. Backfills checked_in_at and initial_check_in_status for attempts that
--      already completed, deriving lateness from the session's late_after_at.
--   3. Renames the status value 'completed' to 'checked_in'.
--   4. Adds CHECK constraints for the frozen vocabulary and for the pairing of
--      checked_in_at with initial_check_in_status.
--
-- NULL statuses are allowed on purpose. The manual-review retry path clears the
-- status to NULL today, and forbidding that here would break the lecturer's
-- retry button. The new attendance model replaces that path later; until then
-- the data it produces stays legal.
--
-- Apply with the Supabase SQL editor or psql. Never put database credentials
-- into this file or into the command used to run it.

BEGIN;

-- 1. Refuse to run against a vocabulary we do not recognise --------------------

DO $$
DECLARE
  unexpected text;
BEGIN
  SELECT string_agg(DISTINCT quote_literal(status), ', ')
  INTO unexpected
  FROM attendance_verification.verification_attempts
  WHERE status IS NOT NULL
    AND status NOT IN ('in_progress', 'checked_in', 'failed', 'completed');

  IF unexpected IS NOT NULL THEN
    RAISE EXCEPTION
      'verification_attempts.status holds unexpected values: %. Resolve these '
      'before applying 20260920_02, or the frozen vocabulary check would '
      'reject them.', unexpected;
  END IF;
END
$$;

-- 2. Backfill the initial check-in of attempts that already completed ----------

-- completed_at is what the old completion endpoint recorded when it accepted
-- the check-in, so it is the closest thing history has to "when the last
-- required step passed". Lateness is recomputed from it against the session's
-- threshold rather than copied from attendance_records, because the old rule
-- compared started_at and therefore marked the wrong students late.
UPDATE attendance_verification.verification_attempts AS attempt
SET checked_in_at = COALESCE(attempt.completed_at, attempt.started_at),
    initial_check_in_status = CASE
      WHEN session.late_after_at IS NOT NULL
       AND COALESCE(attempt.completed_at, attempt.started_at) > session.late_after_at
        THEN 'late_checked_in'
      ELSE 'checked_in'
    END
FROM attendance_session.sessions AS session
WHERE session.id = attempt.session_id
  AND attempt.status = 'completed'
  AND attempt.checked_in_at IS NULL
  AND COALESCE(attempt.completed_at, attempt.started_at) IS NOT NULL;

-- 3. Move to the frozen status vocabulary --------------------------------------

-- 'completed' said the verification process was over. 'checked_in' says what
-- actually happened, and leaves room for the session close to decide attendance
-- afterwards.
UPDATE attendance_verification.verification_attempts
SET status = 'checked_in'
WHERE status = 'completed';

-- 4. Constrain both vocabularies -----------------------------------------------

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'ck_verification_attempts_status'
      AND conrelid = 'attendance_verification.verification_attempts'::regclass
  ) THEN
    ALTER TABLE attendance_verification.verification_attempts
      ADD CONSTRAINT ck_verification_attempts_status
      CHECK (status IS NULL OR status IN ('in_progress', 'checked_in', 'failed'));
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'ck_verification_attempts_initial_check_in_status'
      AND conrelid = 'attendance_verification.verification_attempts'::regclass
  ) THEN
    ALTER TABLE attendance_verification.verification_attempts
      ADD CONSTRAINT ck_verification_attempts_initial_check_in_status
      CHECK (
        initial_check_in_status IS NULL
        OR initial_check_in_status IN ('checked_in', 'late_checked_in')
      );
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'ck_verification_attempts_check_in_pairing'
      AND conrelid = 'attendance_verification.verification_attempts'::regclass
  ) THEN
    -- A check-in is always both a time and an outcome. Half of one would let a
    -- student appear checked in with no recorded moment, or the reverse.
    ALTER TABLE attendance_verification.verification_attempts
      ADD CONSTRAINT ck_verification_attempts_check_in_pairing
      CHECK (
        (checked_in_at IS NULL AND initial_check_in_status IS NULL)
        OR
        (checked_in_at IS NOT NULL AND initial_check_in_status IS NOT NULL)
      );
  END IF;
END
$$;

COMMIT;
