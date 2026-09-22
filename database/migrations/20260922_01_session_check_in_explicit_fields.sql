-- Migration: 20260922_01_session_check_in_explicit_fields
-- Purpose:   Record which of a session's three check-in timestamps
--            (check_in_opens_at, check_in_closes_at, late_after_at) the
--            lecturer explicitly supplied at creation, as opposed to values
--            the active attendance policy filled in.
--
-- Why this is needed: activating a session late must not strand students in a
-- check-in window that already closed, and activating early must not open the
-- window before the lecture is scheduled to start. Fixing that means
-- recomputing the policy-derived fields from the session's effective start at
-- activation time - but a lecturer-supplied value must never be moved, and
-- once a resolved timestamp is stored there is no way to tell "the lecturer
-- typed this" apart from "the policy computed this" just by looking at it.
-- These three flags are that missing fact.
--
-- This is purely additive: every column is nullable-free but defaulted, every
-- existing row backfills to false (see below for why that default is
-- correct), and nothing already running reads these columns. It can be
-- applied at any time before the release that starts writing to them reaches
-- production; applying it after that release would make every session
-- creation fail on a missing column, the same ordering rule documented for
-- 20260920_02.
--
-- Apply with the Supabase SQL editor or psql. Never put database credentials
-- into this file or into the command used to run it.

BEGIN;

ALTER TABLE attendance_session.sessions
  ADD COLUMN IF NOT EXISTS check_in_opens_at_explicit boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS check_in_closes_at_explicit boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS late_after_at_explicit boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN attendance_session.sessions.check_in_opens_at_explicit IS
  'True when the lecturer supplied checkInOpensAt at session creation. False (the default) means the active policy derived it, so activation timing is free to recompute it.';
COMMENT ON COLUMN attendance_session.sessions.check_in_closes_at_explicit IS
  'True when the lecturer supplied checkInClosesAt at session creation. False (the default) means the active policy derived it, so activation timing is free to recompute it.';
COMMENT ON COLUMN attendance_session.sessions.late_after_at_explicit IS
  'True when the lecturer supplied lateAfterAt at session creation. False (the default) means the active policy derived it, so activation timing is free to recompute it.';

-- Every row created before this migration went through the old
-- (pre-Phase-2) creation logic, which never recorded lecturer intent
-- separately from a policy-derived value. Defaulting those rows to false
-- ("derived") is the conservative and correct backfill: it matches the only
-- behaviour that has ever applied to them, and lets a late or early
-- activation on a pre-existing session recompute its window exactly as it
-- would for a newly created one, rather than freezing it as if the lecturer
-- had deliberately pinned every field.

COMMIT;
