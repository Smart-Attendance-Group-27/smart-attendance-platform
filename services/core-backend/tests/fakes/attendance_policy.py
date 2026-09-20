"""A configurable ``AttendancePolicyProvider`` for session-creation tests.

Session and QR creation need to be tested three ways: with a configured policy,
with explicit request values that must win over it, and with no policy at all.
This fake covers all three without Manushan's policy table existing.
"""

from modules.contracts.attendance_policy import AttendancePolicy


class FakeAttendancePolicyProvider:
    """Returns a fixed policy (or none) and counts how often it was read."""

    def __init__(self, policy: AttendancePolicy | None = None) -> None:
        self.policy = policy
        self.read_count = 0

    async def get_active(self, connection) -> AttendancePolicy | None:
        self.read_count += 1
        return self.policy


__all__ = ["FakeAttendancePolicyProvider"]
