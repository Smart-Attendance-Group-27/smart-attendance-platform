BEGIN;

-- ============================================================================
-- 1. Support session cancellation notification type in notification_types
-- ============================================================================
INSERT INTO notification.notification_types (
  code, description,
  default_in_app_enabled, default_push_enabled, default_email_enabled,
  user_configurable, is_active, created_at, updated_at
)
VALUES
  ('ATTENDANCE_SESSION_CANCELLED', 'An attendance session was cancelled', true, true, false, true, true, now(), now())
ON CONFLICT (code) DO UPDATE SET
  description = EXCLUDED.description,
  default_in_app_enabled = EXCLUDED.default_in_app_enabled,
  default_push_enabled = EXCLUDED.default_push_enabled,
  is_active = EXCLUDED.is_active,
  updated_at = now();

-- ============================================================================
-- 2. Performance indexes for active Android device tokens
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_device_tokens_active_user_android
  ON notification.device_tokens (user_id)
  WHERE is_active IS TRUE AND revoked_at IS NULL AND LOWER(platform) = 'android';

-- ============================================================================
-- 3. Performance index for in-app student notification list filtering
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_notifications_recipient_visible
  ON notification.notifications (recipient_user_id, created_at DESC)
  WHERE in_app_visible IS TRUE;

-- ============================================================================
-- 4. Performance indexes for push delivery attempt queue and foreign key
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_delivery_attempts_status_queued
  ON notification.delivery_attempts (delivery_status, queued_at)
  WHERE delivery_status = 'queued';

CREATE INDEX IF NOT EXISTS idx_delivery_attempts_notification_id
  ON notification.delivery_attempts (notification_id);

COMMIT;
