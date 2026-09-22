from collections import defaultdict
from collections.abc import Sequence
from uuid import UUID, uuid4

import asyncpg

from modules.attendance_verification.attendance_state import FinalAttendanceStatus
from modules.contracts.notifications import NotificationProducer as NotificationProducerProtocol
from modules.notification.producer.repository import NotificationProducerRepository


class NotificationProducer(NotificationProducerProtocol):
    """Real NotificationProducer implementation satisfying the I-03 contract.

    Inserts notification rows and queues push delivery attempts in the caller's
    transaction. Never makes external HTTP calls and never opens separate transactions.
    """

    def __init__(self, repository: NotificationProducerRepository | None = None) -> None:
        self._repository = repository or NotificationProducerRepository()

    async def notify_users(
        self,
        connection: asyncpg.Connection,
        *,
        recipient_user_ids: Sequence[UUID],
        type_code: str,
        title: str,
        body: str,
        related_entity_type: str | None = None,
        related_entity_id: UUID | None = None,
        priority: str = "normal",
    ) -> list[UUID]:
        """Creates one notification per recipient, honouring their preferences."""
        if not recipient_user_ids:
            return []

        # Deduplicate while preserving order
        unique_user_ids: list[UUID] = list(dict.fromkeys(recipient_user_ids))

        # 1. Resolve channel preferences for each user
        preferences = await self._repository.fetch_user_preferences(
            connection, unique_user_ids, type_code
        )

        # 2. Check which users have push enabled and fetch their active device tokens
        users_with_push = [
            uid for uid in unique_user_ids if preferences.get(uid, (True, True))[1]
        ]
        tokens_by_user = (
            await self._repository.fetch_active_device_tokens(connection, users_with_push)
            if users_with_push
            else {}
        )

        notification_rows: list[tuple] = []
        attempt_rows: list[tuple] = []
        created_ids: list[UUID] = []

        # 3. Build notification and queued delivery attempt rows
        for user_id in unique_user_ids:
            in_app_enabled, push_enabled = preferences.get(user_id, (True, True))
            if not in_app_enabled and not push_enabled:
                continue

            notification_id = uuid4()
            created_ids.append(notification_id)

            notification_rows.append(
                (
                    notification_id,
                    user_id,
                    type_code,
                    title,
                    body,
                    priority,
                    related_entity_type,
                    related_entity_id,
                    in_app_enabled,  # in_app_visible
                )
            )

            if push_enabled:
                for token_id in tokens_by_user.get(user_id, []):
                    attempt_rows.append((uuid4(), notification_id, token_id))

        # 4. Insert rows transactionally
        await self._repository.insert_notifications_and_attempts(
            connection, notification_rows, attempt_rows
        )

        return created_ids

    async def session_opened(
        self,
        connection: asyncpg.Connection,
        *,
        session_id: UUID,
    ) -> list[UUID]:
        """The lecturer activated the session; the roster can check in."""
        course_name, _ = await self._repository.fetch_session_course_info(connection, session_id)
        enrolled_users = await self._repository.fetch_enrolled_student_user_ids(
            connection, session_id
        )
        if not enrolled_users:
            return []

        return await self.notify_users(
            connection,
            recipient_user_ids=enrolled_users,
            type_code="ATTENDANCE_SESSION_OPENED",
            title="Attendance Session Open",
            body=f"An attendance session for {course_name} is now open. Check in now.",
            related_entity_type="ATTENDANCE_SESSION",
            related_entity_id=session_id,
            priority="high",
        )

    async def qr_batch_activated(
        self,
        connection: asyncpg.Connection,
        *,
        session_id: UUID,
        qr_batch_id: UUID,
        recipient_user_ids: Sequence[UUID],
    ) -> list[UUID]:
        """A QR batch went live; only students who must pass it are told."""
        if not recipient_user_ids:
            return []

        course_name, _ = await self._repository.fetch_session_course_info(connection, session_id)
        return await self.notify_users(
            connection,
            recipient_user_ids=recipient_user_ids,
            type_code="QR_SESSION_ACTIVE",
            title="QR Code Check-in Active",
            body=f"A QR check-in code has been activated for {course_name}. Scan now to record attendance.",
            related_entity_type="ATTENDANCE_SESSION",
            related_entity_id=session_id,
            priority="high",
        )

    async def attendance_finalized(
        self,
        connection: asyncpg.Connection,
        *,
        session_id: UUID,
        results: Sequence[tuple[UUID, FinalAttendanceStatus]],
    ) -> list[UUID]:
        """The session closed; each student is told their final attendance."""
        if not results:
            return []

        course_name, _ = await self._repository.fetch_session_course_info(connection, session_id)
        recipients_by_status: dict[FinalAttendanceStatus, list[UUID]] = defaultdict(list)
        for student_user_id, status in results:
            recipients_by_status[status].append(student_user_id)

        created_ids: list[UUID] = []
        for status, recipient_user_ids in recipients_by_status.items():
            status_str = status.value.capitalize()
            ids = await self.notify_users(
                connection,
                recipient_user_ids=recipient_user_ids,
                type_code="ATTENDANCE_RESULT",
                title="Attendance Recorded",
                body=f"Your attendance for {course_name} has been recorded as {status_str}.",
                related_entity_type="ATTENDANCE_SESSION",
                related_entity_id=session_id,
                priority="normal",
            )
            created_ids.extend(ids)

        return created_ids

    async def attendance_changed(
        self,
        connection: asyncpg.Connection,
        *,
        session_id: UUID,
        student_user_id: UUID,
        status: FinalAttendanceStatus,
    ) -> list[UUID]:
        """A lecturer set or changed one student's attendance by hand."""
        course_name, _ = await self._repository.fetch_session_course_info(connection, session_id)
        status_str = status.value.capitalize()

        return await self.notify_users(
            connection,
            recipient_user_ids=[student_user_id],
            type_code="ATTENDANCE_RESULT",
            title="Attendance Updated",
            body=f"Your attendance for {course_name} was updated to {status_str} by the lecturer.",
            related_entity_type="ATTENDANCE_SESSION",
            related_entity_id=session_id,
            priority="normal",
        )

    async def session_cancelled(
        self,
        connection: asyncpg.Connection,
        *,
        session_id: UUID,
    ) -> list[UUID]:
        """The session was cancelled; no attendance will be recorded for it."""
        course_name, _ = await self._repository.fetch_session_course_info(connection, session_id)
        enrolled_users = await self._repository.fetch_enrolled_student_user_ids(
            connection, session_id
        )
        if not enrolled_users:
            return []

        return await self.notify_users(
            connection,
            recipient_user_ids=enrolled_users,
            type_code="ATTENDANCE_SESSION_CANCELLED",
            title="Attendance Session Cancelled",
            body=f"The attendance session for {course_name} has been cancelled.",
            related_entity_type="ATTENDANCE_SESSION",
            related_entity_id=session_id,
            priority="normal",
        )

    async def upcoming_class_reminders(
        self,
        connection: asyncpg.Connection,
        *,
        lead_minutes: int,
    ) -> int:
        """Idempotently enqueue reminders for scheduled sessions in the window."""
        return await self._repository.enqueue_upcoming_class_reminders(
            connection,
            lead_minutes=lead_minutes,
        )


__all__ = ["NotificationProducer"]
