-- Migration: 20260930_01_session_resilience
-- Purpose:   Session-level verification overrides, automatic session closing,
--            and the left_early final attendance status.
--
-- Depends on 20260920_03_final_attendance_constraints.
--
-- IMPORTANT - APPLY THIS BEFORE DEPLOYING THE MATCHING CODE.
-- The check-in, face-verification and close paths read the new table and
-- column below. Code that ships with this file fails on a database that does
-- not have them yet; the previous release ignores them, so applying this
-- first is safe.
--
-- What it does:
--   1. Adds attendance_session.session_verification_overrides, the source of
--      truth for a verification requirement a lecturer waived for a whole
--      session. Only the geofence factor is allowed for now. One row per
--      session and factor, so a waiver can never be recorded twice.
--   2. Adds attendance_session.sessions.closed_automatically, set when the
--      server closed an overdue session instead of a lecturer, plus a partial
--      index for the overdue-session scan.
--   3. Replaces ck_attendance_records_status so it also allows 'left_early'.
--
-- Apply with the Supabase SQL editor or psql. Never put database credentials
-- into this file or into the command used to run it.

BEGIN;

-- 1. Session verification overrides -------------------------------------------

CREATE TABLE IF NOT EXISTS attendance_session.session_verification_overrides (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL,
  verification_factor character varying(30) NOT NULL,
  scope character varying(20) NOT NULL DEFAULT 'session',
  previous_policy character varying(20) NOT NULL,
  new_policy character varying(20) NOT NULL,
  reason_code character varying(40) NOT NULL,
  reason_text text,
  performed_by uuid NOT NULL,
  performed_at timestamp with time zone NOT NULL DEFAULT now(),
  affected_student_count integer NOT NULL,
  CONSTRAINT pk_session_verification_overrides PRIMARY KEY (id),
  CONSTRAINT fk_session_verification_overrides_session_id
    FOREIGN KEY (session_id) REFERENCES attendance_session.sessions (id),
  CONSTRAINT fk_session_verification_overrides_performed_by
    FOREIGN KEY (performed_by) REFERENCES identity.users (id),
  CONSTRAINT ck_session_verification_overrides_factor
    CHECK (verification_factor IN ('geofence')),
  CONSTRAINT ck_session_verification_overrides_scope
    CHECK (scope IN ('session')),
  CONSTRAINT ck_session_verification_overrides_policy_change
    CHECK (previous_policy = 'required' AND new_policy = 'waived'),
  CONSTRAINT ck_session_verification_overrides_reason_code
    CHECK (reason_code IN (
      'GPS_UNAVAILABLE',
      'GPS_INACCURATE',
      'WRONG_SESSION_LOCATION',
      'DEVICE_LOCATION_FAILURE',
      'OTHER'
    )),
  CONSTRAINT ck_session_verification_overrides_other_reason
    CHECK (
      reason_code <> 'OTHER'
      OR (reason_text IS NOT NULL AND btrim(reason_text) <> '')
    ),
  CONSTRAINT ck_session_verification_overrides_affected_count
    CHECK (affected_student_count >= 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_session_verification_overrides_session_factor
  ON attendance_session.session_verification_overrides (session_id, verification_factor);

COMMENT ON TABLE attendance_session.session_verification_overrides IS
  'A verification requirement waived for an entire attendance session. Verification evidence is never changed by a waiver.';
COMMENT ON COLUMN attendance_session.session_verification_overrides.affected_student_count IS
  'Roster students who had not passed the waived factor when the waiver was recorded.';

-- 2. Automatic session closing ------------------------------------------------

ALTER TABLE attendance_session.sessions
  ADD COLUMN IF NOT EXISTS closed_automatically boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN attendance_session.sessions.closed_automatically IS
  'True when the server closed the session after its scheduled end plus the grace period.';

CREATE INDEX IF NOT EXISTS idx_sessions_open_by_scheduled_end
  ON attendance_session.sessions (scheduled_end_at)
  WHERE activated_at IS NOT NULL AND closed_at IS NULL AND cancelled_at IS NULL;

-- 3. left_early final attendance status ---------------------------------------

ALTER TABLE attendance_verification.attendance_records
  DROP CONSTRAINT IF EXISTS ck_attendance_records_status;

ALTER TABLE attendance_verification.attendance_records
  ADD CONSTRAINT ck_attendance_records_status
  CHECK (attendance_status IN ('present', 'late', 'left_early', 'absent'));

COMMIT;
