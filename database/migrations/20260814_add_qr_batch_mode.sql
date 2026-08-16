ALTER TABLE attendance_session.qr_token_batches
ADD COLUMN IF NOT EXISTS "mode" character varying(20);

ALTER TABLE attendance_session.qr_token_batches
ADD COLUMN IF NOT EXISTS "expires_at" timestamp with time zone;

UPDATE attendance_session.qr_token_batches
SET "mode" = CASE
  WHEN refresh_interval_seconds IS NULL THEN 'static'
  ELSE 'dynamic'
END
WHERE "mode" IS NULL;

UPDATE attendance_session.qr_token_batches AS batch
SET "expires_at" = COALESCE(
  (
    SELECT MIN(token.expires_at)
    FROM attendance_session.qr_tokens AS token
    WHERE token.qr_batch_id = batch.id
  ),
  session.scheduled_end_at
)
FROM attendance_session.sessions AS session
WHERE session.id = batch.session_id
  AND batch."expires_at" IS NULL;

ALTER TABLE attendance_session.qr_token_batches
ALTER COLUMN "mode" SET NOT NULL;

ALTER TABLE attendance_session.qr_token_batches
ALTER COLUMN "expires_at" SET NOT NULL;

ALTER TABLE attendance_session.qr_token_batches
DROP CONSTRAINT IF EXISTS "CK_qr_token_batches_mode";

ALTER TABLE attendance_session.qr_token_batches
ADD CONSTRAINT "CK_qr_token_batches_mode"
CHECK ("mode" IN ('static', 'dynamic'));

ALTER TABLE attendance_session.qr_token_batches
DROP CONSTRAINT IF EXISTS "CK_qr_token_batches_mode_refresh_interval";

ALTER TABLE attendance_session.qr_token_batches
ADD CONSTRAINT "CK_qr_token_batches_mode_refresh_interval"
CHECK (
  ("mode" = 'static' AND "refresh_interval_seconds" IS NULL)
  OR
  ("mode" = 'dynamic' AND "refresh_interval_seconds" IS NOT NULL AND "refresh_interval_seconds" > 0)
);

ALTER TABLE attendance_session.qr_token_batches
DROP CONSTRAINT IF EXISTS "CK_qr_token_batches_expires_after_activation";

ALTER TABLE attendance_session.qr_token_batches
ADD CONSTRAINT "CK_qr_token_batches_expires_after_activation"
CHECK ("expires_at" > "activated_at");
