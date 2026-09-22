BEGIN;

DROP INDEX IF EXISTS notification.idx_delivery_attempts_ready;

ALTER TABLE notification.delivery_attempts
  DROP COLUMN IF EXISTS next_attempt_at;

COMMIT;

