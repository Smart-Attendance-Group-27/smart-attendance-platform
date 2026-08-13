ALTER TABLE attendance_session.qr_token_batches
ADD COLUMN IF NOT EXISTS "mode" character varying(20);

UPDATE attendance_session.qr_token_batches
SET "mode" = CASE
  WHEN refresh_interval_seconds IS NULL THEN 'static'
  ELSE 'dynamic'
END
WHERE "mode" IS NULL;

ALTER TABLE attendance_session.qr_token_batches
ALTER COLUMN "mode" SET NOT NULL;

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
