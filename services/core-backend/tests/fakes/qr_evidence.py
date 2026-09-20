"""An in-memory ``QrEvidenceProvider`` for attendance tests.

Attendance finalization and the lecturer roster read QR progress through the
protocol, so their tests inject this instead of Manushan's repository. That
keeps those tests about attendance rules rather than QR SQL, and it lets the
attendance lifecycle be finished before the real repository exists.
"""

from collections.abc import Mapping
from uuid import UUID

from modules.contracts.qr_evidence import QrRequirementProgress


class FakeQrEvidenceProvider:
    """Returns pre-set QR progress and records which sessions were asked about."""

    def __init__(
        self,
        progress: Mapping[UUID, QrRequirementProgress] | None = None,
    ) -> None:
        self._progress: dict[UUID, QrRequirementProgress] = dict(progress or {})
        self.requested_session_ids: list[UUID] = []

    def set_progress(
        self,
        verification_attempt_id: UUID,
        *,
        required_count: int,
        passed_count: int,
    ) -> None:
        """Gives one verification attempt a QR result."""
        self._progress[verification_attempt_id] = QrRequirementProgress(
            required_count=required_count,
            passed_count=passed_count,
        )

    async def progress_for_session(
        self,
        connection,
        session_id: UUID,
    ) -> Mapping[UUID, QrRequirementProgress]:
        self.requested_session_ids.append(session_id)
        # A copy, so a caller holding the result cannot mutate the fake's state.
        return dict(self._progress)


__all__ = ["FakeQrEvidenceProvider"]
