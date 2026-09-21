BEGIN;

DROP INDEX IF EXISTS notification.idx_delivery_attempts_notification_id;
DROP INDEX IF EXISTS notification.idx_delivery_attempts_status_queued;
DROP INDEX IF EXISTS notification.idx_notifications_recipient_visible;
DROP INDEX IF EXISTS notification.idx_device_tokens_active_user_android;

COMMIT;
