from uuid import UUID

import asyncpg

from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.academic.lecturer_profile.repository import LecturerProfileRepository
from modules.attendance_verification.attendance_state import FinalAttendanceStatus
from modules.attendance_verification.manual_attendance.service import ManualAttendanceService
from modules.attendance_verification.manual_review.exception import (
    VerificationAttemptNotFailedError,
    VerificationAttemptNotFoundError,
)
from modules.attendance_verification.manual_review.repository import (
    FAILED_ATTEMPT_STATUS,
    ManualReviewQueueItemRecord,
    ManualReviewRepository,
)
from modules.attendance_verification.manual_review.schemas import ManualReviewDecision
from modules.audit.repository import write_audit_log

ACTIVE_PROFILE_STATUS = "active"
ACTOR_TYPE_LECTURER = "lecturer"
AUDIT_ACTION = "manual_review.decide"
AUDIT_ENTITY_TYPE = "verification_attempt"


class ManualReviewService:
    def __init__(
        self,
        repository: ManualReviewRepository | None = None,
        lecturer_profile_repository: LecturerProfileRepository | None = None,
        manual_attendance_service: ManualAttendanceService | None = None,
    ) -> None:
        self._repository = repository or ManualReviewRepository()
        self._lecturer_profile_repository = (
            lecturer_profile_repository or LecturerProfileRepository()
        )
        self._manual_attendance_service = manual_attendance_service or ManualAttendanceService()

    async def list_queue_for_user(
        self,
        pool: asyncpg.Pool,
        user_id: UUID,
        session_id: UUID | None = None,
    ) -> list[ManualReviewQueueItemRecord]:
        async with pool.acquire() as connection:
            lecturer_id = await self._resolve_active_lecturer_id(connection, user_id)
            return await self._repository.list_queue_for_lecturer(
                connection,
                lecturer_id,
                session_id=session_id,
            )

    async def decide_for_user(
        self,
        pool: asyncpg.Pool,
        user_id: UUID,
        verification_attempt_id: UUID,
        decision: ManualReviewDecision,
        attendance_status: str | None,
        reason: str,
    ) -> ManualReviewQueueItemRecord:
        if decision is ManualReviewDecision.APPROVE and attendance_status not in (
            FinalAttendanceStatus.PRESENT.value,
            FinalAttendanceStatus.LATE.value,
        ):
            raise ValueError("Approving needs an explicit present or late status.")

        async with pool.acquire() as connection, connection.transaction():
            lecturer_id = await self._resolve_active_lecturer_id(connection, user_id)
            attempt = await self._repository.find_attempt_for_lecturer(
                connection,
                verification_attempt_id,
                lecturer_id,
                lock_for_update=True,
            )
            if attempt is None:
                raise VerificationAttemptNotFoundError()
            if attempt.status != FAILED_ATTEMPT_STATUS:
                raise VerificationAttemptNotFailedError()

            previous_review = await self._repository.find_manual_review(
                connection,
                verification_attempt_id,
            )
            previous_record = await self._repository.find_attendance_record(
                connection,
                attempt.session_id,
                attempt.student_id,
            )

            review_status = decision.value
            final_status = (
                FinalAttendanceStatus(attendance_status)
                if decision is ManualReviewDecision.APPROVE
                else FinalAttendanceStatus.ABSENT
            )
            await self._manual_attendance_service.set_status_in_transaction(
                connection,
                lecturer_user_id=user_id,
                session_id=attempt.session_id,
                student_id=attempt.student_id,
                status=final_status,
                reason=reason,
            )

            await self._repository.upsert_manual_review(
                connection,
                verification_attempt_id=verification_attempt_id,
                review_status=review_status,
                reviewed_by=user_id,
                decision_reason=reason,
            )

            await write_audit_log(
                connection,
                actor_user_id=user_id,
                actor_type=ACTOR_TYPE_LECTURER,
                action=AUDIT_ACTION,
                entity_type=AUDIT_ENTITY_TYPE,
                entity_id=verification_attempt_id,
                old_values={
                    "reviewStatus": previous_review.review_status if previous_review else None,
                    "attendanceStatus": (
                        previous_record.attendance_status if previous_record else None
                    ),
                },
                new_values={"reviewStatus": review_status, "decision": decision.value},
                metadata={"sessionId": str(attempt.session_id), "studentId": str(attempt.student_id)},
            )

            item = await self._repository.find_queue_item_for_lecturer(
                connection,
                verification_attempt_id,
                lecturer_id,
            )

        assert item is not None
        return item

    async def _resolve_active_lecturer_id(
        self,
        connection: asyncpg.Connection,
        user_id: UUID,
    ) -> UUID:
        profile = await self._lecturer_profile_repository.find_by_user_id(connection, user_id)
        if profile is None or profile.profile_status != ACTIVE_PROFILE_STATUS:
            raise LecturerProfileNotFoundError("No active lecturer profile exists for this account.")
        return profile.id
