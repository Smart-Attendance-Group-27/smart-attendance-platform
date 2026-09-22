BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS uq_notifications_upcoming_class_session_user
  ON notification.notifications (
    recipient_user_id,
    related_entity_id,
    notification_type
  )
  WHERE notification_type = 'UPCOMING_CLASS'
    AND related_entity_type = 'ATTENDANCE_SESSION';

COMMIT;
