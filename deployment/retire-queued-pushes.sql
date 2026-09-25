-- Run with psql -v ON_ERROR_STOP=1 -v cutoff='2026-09-25T16:00:00Z'
-- immediately before enabling the push worker. Use the actual activation time.
-- Only pending push attempts before cutoff are removed. In-app notifications stay.
BEGIN;
WITH retired AS (
  DELETE FROM notification.delivery_attempts
  WHERE channel = 'push'
    AND delivery_status = 'queued'
    AND queued_at < :'cutoff'::timestamptz
  RETURNING id
)
SELECT count(*) AS retired_queued_pushes FROM retired;
COMMIT;
