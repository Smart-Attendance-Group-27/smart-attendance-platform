from collections import defaultdict
from collections.abc import Sequence
from uuid import UUID

import asyncpg


class NotificationProducerRepository:
    """Transactional database access for NotificationProducer."""

    async def fetch_user_preferences(
        self,
        connection: asyncpg.Connection,
        user_ids: Sequence[UUID],
        type_code: str,
    ) -> dict[UUID, tuple[bool, bool]]:
        """Resolve (in_app_enabled, push_enabled) for each user.

        Honours custom user preferences where set, falling back to the
        notification type defaults. If the notification type is inactive,
        both channels resolve to False.
        """
        if not user_ids:
            return {}

        rows = await connection.fetch(
            """
            SELECT
                u.id AS user_id,
                COALESCE(nt.is_active, true) AS type_is_active,
                COALESCE(np.in_app_enabled, nt.default_in_app_enabled, true) AS in_app_enabled,
                COALESCE(np.push_enabled, nt.default_push_enabled, true) AS push_enabled
            FROM unnest($1::uuid[]) AS u(id)
            LEFT JOIN notification.notification_types nt
                ON nt.code = $2
            LEFT JOIN notification.notification_preferences np
                ON np.user_id = u.id AND np.notification_type = $2;
            """,
            list(user_ids),
            type_code,
        )

        preferences: dict[UUID, tuple[bool, bool]] = {}
        for row in rows:
            uid = row["user_id"]
            if not row["type_is_active"]:
                preferences[uid] = (False, False)
            else:
                preferences[uid] = (bool(row["in_app_enabled"]), bool(row["push_enabled"]))

        return preferences

    async def fetch_active_device_tokens(
        self,
        connection: asyncpg.Connection,
        user_ids: Sequence[UUID],
    ) -> dict[UUID, list[UUID]]:
        """Return a mapping of user_id -> list of active Android device_token_ids."""
        if not user_ids:
            return {}

        rows = await connection.fetch(
            """
            SELECT id, user_id
            FROM notification.device_tokens
            WHERE user_id = ANY($1::uuid[])
              AND is_active IS TRUE
              AND revoked_at IS NULL
              AND LOWER(platform) = 'android';
            """,
            list(user_ids),
        )

        tokens_by_user: dict[UUID, list[UUID]] = defaultdict(list)
        for row in rows:
            tokens_by_user[row["user_id"]].append(row["id"])

        return dict(tokens_by_user)

    async def insert_notifications_and_attempts(
        self,
        connection: asyncpg.Connection,
        notifications: list[tuple],
        attempts: list[tuple],
    ) -> None:
        """Insert notification and delivery_attempt rows in the caller's transaction."""
        if notifications:
            await connection.executemany(
                """
                INSERT INTO notification.notifications (
                    id,
                    recipient_user_id,
                    notification_type,
                    title,
                    body,
                    priority,
                    related_entity_type,
                    related_entity_id,
                    in_app_visible,
                    created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, now());
                """,
                notifications,
            )

        if attempts:
            await connection.executemany(
                """
                INSERT INTO notification.delivery_attempts (
                    id,
                    notification_id,
                    channel,
                    device_token_id,
                    attempt_number,
                    delivery_status,
                    queued_at
                ) VALUES ($1, $2, 'push', $3, 0, 'queued', now());
                """,
                attempts,
            )

    async def fetch_session_course_info(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
    ) -> tuple[str, str]:
        """Return (course_name, course_code) for the given attendance session."""
        row = await connection.fetchrow(
            """
            SELECT
                c.course_name,
                c.course_code
            FROM attendance_session.sessions s
            JOIN academic.course_offerings co ON co.id = s.course_offering_id
            JOIN academic.courses c ON c.id = co.course_id
            WHERE s.id = $1;
            """,
            session_id,
        )
        if row:
            return row["course_name"] or "your course", row["course_code"] or ""
        return "your course", ""

    async def fetch_enrolled_student_user_ids(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
    ) -> list[UUID]:
        """Return the user IDs of all students enrolled in the session."""
        rows = await connection.fetch(
            """
            SELECT DISTINCT sp.user_id
            FROM attendance_session.session_students ss
            JOIN academic.student_profiles sp ON sp.id = ss.student_id
            WHERE ss.session_id = $1;
            """,
            session_id,
        )
        return [row["user_id"] for row in rows]
