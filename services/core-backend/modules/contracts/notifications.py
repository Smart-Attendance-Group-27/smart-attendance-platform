"""The notification contract consumed by the attendance and QR modules.

Ashen owns the notification module and implements this protocol as
``modules.notification.producer.service.NotificationProducer``. Attendance and
QR code only ever call the protocol, so the trigger call sites can be written
and tested before the real producer exists: they run against
``NoOpNotificationProducer`` in production until INT-3 binds the real one (see
``providers.py``), and against ``RecordingNotificationProducer`` in tests.

Every method takes the caller's connection and only inserts rows. A producer
never sends anything itself and never opens its own transaction, so a
notification is written exactly when the attendance change that caused it
commits, and disappears with it on rollback. Delivery is a separate worker.

Each method returns the ids of the notifications it created.
"""

from collections.abc import Sequence
from typing import Protocol, runtime_checkable
from uuid import UUID

import asyncpg

from modules.attendance_verification.attendance_state import FinalAttendanceStatus


@runtime_checkable
class NotificationProducer(Protocol):
    """Creates in-app notifications (and queues their pushes) for students."""

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
        ...

    async def session_opened(
        self,
        connection: asyncpg.Connection,
        *,
        session_id: UUID,
    ) -> list[UUID]:
        """The lecturer activated the session; the roster can check in."""
        ...

    async def qr_batch_activated(
        self,
        connection: asyncpg.Connection,
        *,
        session_id: UUID,
        qr_batch_id: UUID,
        recipient_user_ids: Sequence[UUID],
    ) -> list[UUID]:
        """A QR batch went live; only students who must pass it are told."""
        ...

    async def attendance_finalized(
        self,
        connection: asyncpg.Connection,
        *,
        session_id: UUID,
        results: Sequence[tuple[UUID, FinalAttendanceStatus]],
    ) -> list[UUID]:
        """The session closed; each student is told their final attendance.

        ``results`` pairs each student's *user* id (``identity.users.id``, the
        account that receives the notification, not the student profile id)
        with the status that was decided. It holds only the automatic
        decisions: a student whose attendance a lecturer already set by hand
        was told through ``attendance_changed`` when that happened.
        """
        ...

    async def attendance_changed(
        self,
        connection: asyncpg.Connection,
        *,
        session_id: UUID,
        student_user_id: UUID,
        status: FinalAttendanceStatus,
    ) -> list[UUID]:
        """A lecturer set or changed one student's attendance by hand."""
        ...

    async def session_cancelled(
        self,
        connection: asyncpg.Connection,
        *,
        session_id: UUID,
    ) -> list[UUID]:
        """The session was cancelled; no attendance will be recorded for it."""
        ...


class NoOpNotificationProducer:
    """The producer bound in production until Ashen's real one arrives (INT-3).

    Call sites can ship and run without notifications existing yet: every call
    is accepted and creates nothing.
    """

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
        return []

    async def session_opened(
        self,
        connection: asyncpg.Connection,
        *,
        session_id: UUID,
    ) -> list[UUID]:
        return []

    async def qr_batch_activated(
        self,
        connection: asyncpg.Connection,
        *,
        session_id: UUID,
        qr_batch_id: UUID,
        recipient_user_ids: Sequence[UUID],
    ) -> list[UUID]:
        return []

    async def attendance_finalized(
        self,
        connection: asyncpg.Connection,
        *,
        session_id: UUID,
        results: Sequence[tuple[UUID, FinalAttendanceStatus]],
    ) -> list[UUID]:
        return []

    async def attendance_changed(
        self,
        connection: asyncpg.Connection,
        *,
        session_id: UUID,
        student_user_id: UUID,
        status: FinalAttendanceStatus,
    ) -> list[UUID]:
        return []

    async def session_cancelled(
        self,
        connection: asyncpg.Connection,
        *,
        session_id: UUID,
    ) -> list[UUID]:
        return []


__all__ = ["NoOpNotificationProducer", "NotificationProducer"]
