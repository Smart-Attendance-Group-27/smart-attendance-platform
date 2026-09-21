-- Rollback: 20260920_03_final_attendance_constraints
--
-- Drops the three constraints and puts the record source back the way the
-- previous release wrote it, so that release can serve traffic again. Run this
-- before redeploying that code, not after.
--
-- Every 'manual' record goes back to 'manual_review', including any written
-- through the direct edit endpoint since the release. The previous release only
-- knows one name for a lecturer's decision, and leaving these as 'manual' would
-- make it treat them as something else. Nothing else about the records changes.

BEGIN;

ALTER TABLE attendance_verification.attendance_records
  DROP CONSTRAINT IF EXISTS ck_attendance_records_manual_fields;

ALTER TABLE attendance_verification.attendance_records
  DROP CONSTRAINT IF EXISTS ck_attendance_records_source;

ALTER TABLE attendance_verification.attendance_records
  DROP CONSTRAINT IF EXISTS ck_attendance_records_status;

UPDATE attendance_verification.attendance_records
SET record_source = 'manual_review'
WHERE record_source = 'manual';

COMMIT;
