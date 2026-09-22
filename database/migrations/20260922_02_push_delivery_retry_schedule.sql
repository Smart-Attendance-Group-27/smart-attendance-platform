BEGIN;

ALTER TABLE notification.delivery_attempts
  ADD COLUMN IF NOT EXISTS next_attempt_at timestamp with time zone;

-- The retired request-side orchestrator used "pending" for the same state.
UPDATE notification.delivery_attempts
SET delivery_status = 'queued'
WHERE delivery_status = 'pending';

CREATE INDEX IF NOT EXISTS idx_delivery_attempts_ready
  ON notification.delivery_attempts (delivery_status, next_attempt_at, queued_at)
  WHERE delivery_status IN ('queued', 'in_flight', 'sent');

COMMIT;

