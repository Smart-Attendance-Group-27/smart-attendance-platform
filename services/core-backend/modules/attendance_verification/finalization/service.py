from datetime import datetime
from uuid import UUID

import asyncpg

from modules.attendance_sessions.qr_session.cache import QrBatchMetadataCache
from modules.attendance_verification.attendance_state import FinalAttendanceStatus, InitialCheckInStatus
from modules.attendance_verification.check_in.service import CheckInService
from modules.attendance_verification.finalization.repository import FinalizationRepository
from modules.attendance_verification.finalization.types import (
    FinalizationResult,
    FinalizationSummary,
    decide_final_attendance,
)
from modules.contracts.qr_evidence import QrEvidenceProvider


class AttendanceFinalizationService:
    """Decides and writes attendance for every roster student, once.

    Requires a bound ``QrEvidenceProvider`` — there is no "finalize without QR"
    mode. A caller with no provider bound must not construct this at all and
    should treat finalization as unavailable instead; see
    ``LecturerSessionService.close_for_user``.
    """

    def __init__(
        self,
        qr_evidence: QrEvidenceProvider,
        check_in_service: CheckInService | None = None,
        repository: FinalizationRepository | None = None,
    ) -> None:
        self._qr_evidence = qr_evidence
        self._check_in_service = check_in_service or CheckInService()
        self._repository = repository or FinalizationRepository()

    async def finalize(
        self,
        connection: asyncpg.Connection,
        *,
        session_id: UUID,
        closed_at: datetime,
        actor_user_id: UUID,  # noqa: ARG002 - part of the frozen I-07 signature
    ) -> FinalizationSummary:
        await self._repository.lock_session_attempts(connection, session_id)

        reconciled = await self._check_in_service.reconcile_before_close(
            connection,
            session_id,
            closed_at,
        )
        reconciled_student_ids = tuple(entry.student_id for entry in reconciled)

        roster = await self._repository.fetch_roster_state(connection, session_id)
        qr_progress = await self._qr_evidence.progress_for_session(connection, session_id)

        results: list[FinalizationResult] = []
        kept_manual = 0
        for student in roster:
            if student.has_manual_record:
                kept_manual += 1
                continue

            progress = (
                qr_progress.get(student.verification_attempt_id)
                if student.verification_attempt_id is not None
                else None
            )
            status = decide_final_attendance(
                initial_check_in_status=_parse_initial_check_in_status(
                    student.initial_check_in_status,
                ),
                qr_progress=progress,
            )
            results.append(FinalizationResult(student_id=student.student_id, status=status))

        await self._repository.upsert_automatic_records(
            connection,
            session_id,
            results,
            closed_at,
        )

        return FinalizationSummary(
            enrolled=len(roster),
            present=_count(results, FinalAttendanceStatus.PRESENT),
            late=_count(results, FinalAttendanceStatus.LATE),
            absent=_count(results, FinalAttendanceStatus.ABSENT),
            kept_manual=kept_manual,
            reconciled_student_ids=reconciled_student_ids,
            # Filled in by the caller — see FinalizationSummary's docstring.
            deactivated_qr_batch_ids=(),
            results=tuple(results),
            finalized_at=closed_at,
        )

    @staticmethod
    async def after_commit(summary: FinalizationSummary, redis_client) -> None:
        cache = QrBatchMetadataCache(redis_client)
        for batch_id in summary.deactivated_qr_batch_ids:
            await cache.delete_qr_batch_cache(batch_id)


def _count(results: list[FinalizationResult], status: FinalAttendanceStatus) -> int:
    return sum(1 for result in results if result.status is status)


def _parse_initial_check_in_status(value: str | None) -> InitialCheckInStatus | None:
    if value is None:
        return None
    try:
        return InitialCheckInStatus(value)
    except ValueError:
        # Outside the frozen vocabulary. MIG-B's CHECK constraint should make
        # this unreachable; treat it as on-time rather than crash finalization.
        return InitialCheckInStatus.CHECKED_IN


__all__ = ["AttendanceFinalizationService"]
