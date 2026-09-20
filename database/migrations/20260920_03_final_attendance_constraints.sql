-- Migration: 20260920_03_final_attendance_constraints
-- Purpose:   Settle the vocabulary of final attendance records and constrain it.
--
-- Depends on the two migrations before it, and on the code that writes
-- record_source = 'manual'.
--
-- IMPORTANT - APPLY THIS WITH THE MATCHING CODE, NOT BEFORE IT.
-- Like 20260920_02 this is not additive. It renames the stored record source
-- 'manual_review' to 'manual' and then only allows 'automatic' and 'manual'.
-- The release that ships with this file writes 'manual'; the previous release
-- wrote 'manual_review', which the constraint below would reject.
--
-- What it does:
--   1. Refuses to run if attendance_records holds a value this migration does
--      not know about, or a manual row with no recorder or no reason, naming
--      what it found.
--   2. Renames record_source 'manual_review' to 'manual'.
--   3. Adds CHECK constraints for the status and source vocabularies and for
--      the fields a manual record must carry.
--
-- Apply with the Supabase SQL editor or psql. Never put database credentials
-- into this file or into the command used to run it.

BEGIN;

-- 1. Refuse to run against data we do not recognise ---------------------------

DO $$
DECLARE
  unexpected_status text;
  unexpected_source text;
  incomplete_manual bigint;
BEGIN
  SELECT string_agg(DISTINCT quote_literal(COALESCE(attendance_status, 'NULL')), ', ')
  INTO unexpected_status
  FROM attendance_verification.attendance_records
  WHERE attendance_status IS NULL
     OR attendance_status NOT IN ('present', 'late', 'absent');

  IF unexpected_status IS NOT NULL THEN
    RAISE EXCEPTION
      'attendance_records.attendance_status holds unexpected values: %. Resolve '
      'these before applying 20260920_03.', unexpected_status;
  END IF;

  SELECT string_agg(DISTINCT quote_literal(COALESCE(record_source, 'NULL')), ', ')
  INTO unexpected_source
  FROM attendance_verification.attendance_records
  WHERE record_source IS NULL
     OR record_source NOT IN ('automatic', 'manual', 'manual_review');

  IF unexpected_source IS NOT NULL THEN
    RAISE EXCEPTION
      'attendance_records.record_source holds unexpected values: %. Resolve '
      'these before applying 20260920_03.', unexpected_source;
  END IF;

  SELECT count(*)
  INTO incomplete_manual
  FROM attendance_verification.attendance_records
  WHERE record_source IN ('manual', 'manual_review')
    AND (
      recorded_by IS NULL
      OR manual_reason IS NULL
      OR btrim(manual_reason) = ''
    );

  IF incomplete_manual > 0 THEN
    RAISE EXCEPTION
      '% manual attendance record(s) have no recorder or no reason. Fill them '
      'in before applying 20260920_03.', incomplete_manual;
  END IF;
END
$$;

-- 2. One name for a lecturer's decision ---------------------------------------

-- Both manual paths (the direct edit and manual review) now write 'manual'.
UPDATE attendance_verification.attendance_records
SET record_source = 'manual'
WHERE record_source = 'manual_review';

-- 3. Constrain the vocabularies -----------------------------------------------

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'ck_attendance_records_status'
      AND conrelid = 'attendance_verification.attendance_records'::regclass
  ) THEN
    ALTER TABLE attendance_verification.attendance_records
      ADD CONSTRAINT ck_attendance_records_status
      CHECK (attendance_status IN ('present', 'late', 'absent'));
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'ck_attendance_records_source'
      AND conrelid = 'attendance_verification.attendance_records'::regclass
  ) THEN
    ALTER TABLE attendance_verification.attendance_records
      ADD CONSTRAINT ck_attendance_records_source
      CHECK (record_source IN ('automatic', 'manual'));
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'ck_attendance_records_manual_fields'
      AND conrelid = 'attendance_verification.attendance_records'::regclass
  ) THEN
    -- A manual decision is always attributable and always explained.
    ALTER TABLE attendance_verification.attendance_records
      ADD CONSTRAINT ck_attendance_records_manual_fields
      CHECK (
        record_source <> 'manual'
        OR (
          recorded_by IS NOT NULL
          AND manual_reason IS NOT NULL
          AND btrim(manual_reason) <> ''
        )
      );
  END IF;
END
$$;

COMMIT;
