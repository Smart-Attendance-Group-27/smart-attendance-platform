-- Rollback: 20260922_01_session_check_in_explicit_fields
--
-- Drops the three explicit-field flags added by the migration. Safe as long
-- as no release depends on them yet: activation-time recompute (Phase 2,
-- Commit 3) reads these columns, so this rollback must run before that code
-- is deployed, never after - the same ordering constraint the migration
-- itself documents in reverse.
--
-- Dropping these columns loses only the "was this explicit" bookkeeping.
-- check_in_opens_at, check_in_closes_at and late_after_at themselves are
-- untouched, so no attendance timing data is lost - a session simply goes
-- back to not distinguishing lecturer intent from policy-derived defaults.

BEGIN;

ALTER TABLE attendance_session.sessions
  DROP COLUMN IF EXISTS late_after_at_explicit,
  DROP COLUMN IF EXISTS check_in_closes_at_explicit,
  DROP COLUMN IF EXISTS check_in_opens_at_explicit;

COMMIT;
