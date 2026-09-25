from uuid import UUID

import asyncpg

from modules.academic.admin_correction_requests.exception import (
    CorrectionRequestNotFoundError,
    InvalidDecisionError,
    InvalidReviewNoteError,
)
from modules.academic.admin_correction_requests.repository import (
    AdminCorrectionRequestRecord,
    AdminCorrectionRequestRepository,
)
from modules.academic.admin_correction_requests.schemas import ReviewDecision
from modules.audit.repository import write_audit_log

ACTOR_TYPE_ADMINISTRATOR = "administrator"
AUDIT_ACTION = "correction_request.decided"
AUDIT_ENTITY_TYPE = "correction_request"
MAX_NOTE_LENGTH = 1000
MIN_REJECTION_NOTE_LENGTH = 3

# A request is approved or rejected once, and an approved one is later marked
# resolved when the administrator has made the change in the academic data.
_ALLOWED_DECISIONS = {
    "pending": {ReviewDecision.APPROVED, ReviewDecision.REJECTED},
    "approved": {ReviewDecision.RESOLVED},
}


class AdminCorrectionRequestService:
    """Lets administrators review lecturer correction requests.

    Deciding a request never edits the academic data itself; the administrator
    makes the actual change through the normal academic-data screens.
    """

    def __init__(self, repository: AdminCorrectionRequestRepository | None = None) -> None:
        self._repository = repository or AdminCorrectionRequestRepository()

    async def list_requests(
        self,
        pool: asyncpg.Pool,
        *,
        status: str | None,
    ) -> list[AdminCorrectionRequestRecord]:
        async with pool.acquire() as connection:
            return await self._repository.list_requests(connection, status=status)

    async def decide(
        self,
        pool: asyncpg.Pool,
        *,
        actor_user_id: UUID,
        request_id: UUID,
        decision: ReviewDecision,
        note: str,
    ) -> AdminCorrectionRequestRecord:
        note = note.strip()
        if len(note) > MAX_NOTE_LENGTH:
            raise InvalidReviewNoteError("The note is too long.")
        if decision is ReviewDecision.REJECTED and len(note) < MIN_REJECTION_NOTE_LENGTH:
            raise InvalidReviewNoteError("Give the lecturer a reason for rejecting the request.")

        async with pool.acquire() as connection, connection.transaction():
            current_status = await self._repository.lock_status(connection, request_id)
            if current_status is None:
                raise CorrectionRequestNotFoundError()
            if decision not in _ALLOWED_DECISIONS.get(current_status, set()):
                raise InvalidDecisionError(
                    f"A {current_status} request cannot be marked {decision.value}."
                )

            await self._repository.record_decision(
                connection,
                request_id,
                status=decision.value,
                reviewed_by=actor_user_id,
                review_note=note or None,
            )
            await write_audit_log(
                connection,
                actor_user_id=actor_user_id,
                actor_type=ACTOR_TYPE_ADMINISTRATOR,
                action=AUDIT_ACTION,
                entity_type=AUDIT_ENTITY_TYPE,
                entity_id=request_id,
                old_values={"status": current_status},
                new_values={"status": decision.value, "note": note or None},
            )
            updated = await self._repository.find_request(connection, request_id)
            assert updated is not None
            return updated
