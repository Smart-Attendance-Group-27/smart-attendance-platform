"""The attendance policy contract consumed when a session is created.

Manushan owns the policy module and implements this protocol as
``modules.academic.attendance_policy.repository.AttendancePolicyRepository``,
backed by ``academic.attendance_policies``. Session creation and QR batch
creation only depend on the protocol, so they can be written before that table
exists: ``DefaultAttendancePolicyProvider`` returns ``None`` until INT-4 binds
the real repository (see ``providers.py``).

``None`` means "no policy configured", and every consumer must then keep its
existing built-in default rather than inventing one here.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import asyncpg


@dataclass(frozen=True, slots=True)
class AttendancePolicy:
    """The institution-wide defaults an administrator configures."""

    check_in_window_minutes: int
    late_threshold_minutes: int
    qr_default_validity_minutes: int


@runtime_checkable
class AttendancePolicyProvider(Protocol):
    """Reads the single active attendance policy."""

    async def get_active(
        self,
        connection: asyncpg.Connection,
    ) -> AttendancePolicy | None:
        """Returns the active policy, or None when none is configured."""
        ...


class DefaultAttendancePolicyProvider:
    """The provider bound in production until the policy table exists (INT-4).

    It reports "no policy configured", which keeps session and QR creation on
    the defaults they use today.
    """

    async def get_active(
        self,
        connection: asyncpg.Connection,
    ) -> AttendancePolicy | None:
        return None


__all__ = [
    "AttendancePolicy",
    "AttendancePolicyProvider",
    "DefaultAttendancePolicyProvider",
]
