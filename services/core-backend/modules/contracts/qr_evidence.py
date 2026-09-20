"""The QR evidence contract consumed by attendance finalization and the roster.

Manushan owns the QR module and implements this protocol as
``modules.attendance_sessions.qr_session.evidence.QrEvidenceRepository``. The
attendance lifecycle only ever depends on the protocol, so both sides can be
built at the same time: attendance code develops against a fake and the real
repository is bound in one line at INT-1 (see ``providers.py``).

The rule the implementation must follow is frozen:

* a QR batch is REQUIRED for a student when it belongs to the student's session,
  ``batch.activated_at > attempt.checked_in_at`` (strictly greater), and the
  batch is not voided;
* a required batch is PASSED when at least one ``qr_validation_attempts`` row
  exists for that ``(verification_attempt_id, qr_batch_id)`` with
  ``validation_status = 'accepted'``.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from uuid import UUID

import asyncpg


@dataclass(frozen=True, slots=True)
class QrRequirementProgress:
    """How many QR batches a student must pass, and how many they have passed."""

    required_count: int
    passed_count: int

    @property
    def is_satisfied(self) -> bool:
        """True when no required batch is outstanding (including "none required")."""
        return self.passed_count >= self.required_count


@runtime_checkable
class QrEvidenceProvider(Protocol):
    """Reads per-batch QR evidence for one attendance session."""

    async def progress_for_session(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
    ) -> Mapping[UUID, QrRequirementProgress]:
        """Returns the QR progress of every checked-in student in the session.

        The mapping is keyed by ``verification_attempts.id``. Attempts that are
        not checked in are left out, because a student who never checked in has
        no required batches to begin with.

        The implementation must run on the connection it is given and must not
        open a transaction of its own: finalization calls this after it has
        reconciled check-ins inside the close transaction, and those rows have
        to be visible to this query.
        """
        ...


__all__ = ["QrEvidenceProvider", "QrRequirementProgress"]
