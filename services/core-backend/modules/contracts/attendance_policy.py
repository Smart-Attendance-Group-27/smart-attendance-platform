"""The attendance policy contract consumed when a session is created.

Manushan owns the policy module and implements this protocol as
``modules.academic.attendance_policy.repository.AttendancePolicyRepository``,
backed by ``academic.attendance_policies``. Session creation and QR batch
creation depend only on this protocol; INT-4 binds the real repository in
``providers.py``. ``DefaultAttendancePolicyProvider`` remains available for
isolated service tests.

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
    """Reports no configured policy for isolated consumers and tests."""

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
