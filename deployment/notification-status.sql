-- Read-only notification delivery summary. Run with psql against the application DB.
SELECT delivery_status, count(*) AS attempts,
       min(queued_at) AS oldest_queued_at,
       max(queued_at) AS newest_queued_at
FROM notification.delivery_attempts
GROUP BY delivery_status
ORDER BY delivery_status;

SELECT count(*) FILTER (WHERE delivery_status = 'queued') AS queued,
       count(*) FILTER (WHERE delivery_status = 'queued'
                       AND queued_at < now() - interval '15 minutes') AS queued_older_than_15_minutes,
       count(*) FILTER (WHERE delivery_status = 'failed'
                       AND completed_at > now() - interval '24 hours') AS failed_last_24_hours,
       count(*) FILTER (WHERE delivery_status = 'delivered'
                       AND completed_at > now() - interval '24 hours') AS delivered_last_24_hours
FROM notification.delivery_attempts;

SELECT count(*) AS active_android_tokens
FROM notification.device_tokens
WHERE is_active IS TRUE AND revoked_at IS NULL AND lower(platform) = 'android';

SELECT notification_type, count(*) AS notifications_last_24_hours
FROM notification.notifications
WHERE created_at > now() - interval '24 hours'
GROUP BY notification_type
ORDER BY notification_type;
