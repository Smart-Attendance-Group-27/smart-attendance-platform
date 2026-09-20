"""A recording ``NotificationProducer`` for attendance and QR tests.

The trigger call sites are tested by asserting what they announced and to whom,
which is the part the attendance and QR modules own. Building the message text,
honouring preferences and delivering the push all belong to Ashen's producer
and are tested there.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from modules.attendance_verification.attendance_state import FinalAttendanceStatus


@dataclass(frozen=True, slots=True)
class RecordedNotification:
    """One producer call: which trigger fired, and what it carried."""

    kind: str
    payload: dict[str, object] = field(default_factory=dict)


class RecordingNotificationProducer:
    """Records every trigger instead of creating notifications."""

    def __init__(self) -> None:
        self.calls: list[RecordedNotification] = []

    # -- helpers for assertions -------------------------------------------------

    @property
    def kinds(self) -> list[str]:
        """The triggers that fired, in order."""
        return [call.kind for call in self.calls]

    def calls_of(self, kind: str) -> list[RecordedNotification]:
        """Every recorded call of one trigger."""
        return [call for call in self.calls if call.kind == kind]

    def only_call_of(self, kind: str) -> RecordedNotification:
        """The single recorded call of one trigger, or an assertion failure."""
        matching = self.calls_of(kind)
        if len(matching) != 1:
            raise AssertionError(
                f"expected exactly one {kind!r} notification, got {len(matching)}",
            )
        return matching[0]

    # -- NotificationProducer ---------------------------------------------------

    async def notify_users(
        self,
        connection,
        *,
        recipient_user_ids: Sequence[UUID],
        type_code: str,
        title: str,
        body: str,
        related_entity_type: str | None = None,
        related_entity_id: UUID | None = None,
        priority: str = "normal",
    ) -> list[UUID]:
        self.calls.append(
            RecordedNotification(
                kind="notify_users",
                payload={
                    "recipient_user_ids": list(recipient_user_ids),
                    "type_code": type_code,
                    "title": title,
                    "body": body,
                    "related_entity_type": related_entity_type,
                    "related_entity_id": related_entity_id,
                    "priority": priority,
                },
            ),
        )
        return [uuid4() for _ in recipient_user_ids]

    async def session_opened(self, connection, *, session_id: UUID) -> list[UUID]:
        self.calls.append(
            RecordedNotification(kind="session_opened", payload={"session_id": session_id}),
        )
        # The real producer resolves the roster itself, so the fake cannot know
        # how many notifications that would be.
        return []

    async def qr_batch_activated(
        self,
        connection,
        *,
        session_id: UUID,
        qr_batch_id: UUID,
        recipient_user_ids: Sequence[UUID],
    ) -> list[UUID]:
        self.calls.append(
            RecordedNotification(
                kind="qr_batch_activated",
                payload={
                    "session_id": session_id,
                    "qr_batch_id": qr_batch_id,
                    "recipient_user_ids": list(recipient_user_ids),
                },
            ),
        )
        return [uuid4() for _ in recipient_user_ids]

    async def attendance_finalized(
        self,
        connection,
        *,
        session_id: UUID,
        results: Sequence[tuple[UUID, FinalAttendanceStatus]],
    ) -> list[UUID]:
        self.calls.append(
            RecordedNotification(
                kind="attendance_finalized",
                payload={"session_id": session_id, "results": list(results)},
            ),
        )
        return [uuid4() for _ in results]

    async def attendance_changed(
        self,
        connection,
        *,
        session_id: UUID,
        student_user_id: UUID,
        status: FinalAttendanceStatus,
    ) -> list[UUID]:
        self.calls.append(
            RecordedNotification(
                kind="attendance_changed",
                payload={
                    "session_id": session_id,
                    "student_user_id": student_user_id,
                    "status": status,
                },
            ),
        )
        return [uuid4()]

    async def session_cancelled(self, connection, *, session_id: UUID) -> list[UUID]:
        self.calls.append(
            RecordedNotification(
                kind="session_cancelled",
                payload={"session_id": session_id},
            ),
        )
        return []


__all__ = ["RecordedNotification", "RecordingNotificationProducer"]
