from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from modules.attendance_verification.geofence.repository import (
    IN_PROGRESS_STATUS,
    GeofenceRepository,
)
from modules.attendance_verification.geofence.types import (
    GeofenceDecision,
    GeofenceNextStep,
    GeofenceReason,
    GeofenceValidationResult,
)

USER_ID = UUID("20000000-0000-0000-0000-000000000011")
STUDENT_ID = UUID("23000000-0000-0000-0000-000000000001")
SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
VERIFICATION_ATTEMPT_ID = UUID("50000000-0000-0000-0000-000000000001")
GEOFENCE_ATTEMPT_ID = UUID("51000000-0000-0000-0000-000000000001")
CURRENT_TIME = datetime(2026, 8, 13, 5, 30, tzinfo=UTC)


class FakeConnection:
    def __init__(
        self,
        *,
        fetchrow_result: dict[str, Any] | None = None,
        fetchval_result: Any = None,
    ) -> None:
        self.fetchrow_result = fetchrow_result
        self.fetchval_result = fetchval_result
        self.calls: list[tuple[str, str, tuple[Any, ...]]] = []

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        self.calls.append(("fetchrow", query, args))
        return self.fetchrow_result

    async def fetchval(self, query: str, *args: Any) -> Any:
        self.calls.append(("fetchval", query, args))
        return self.fetchval_result

    async def execute(self, query: str, *args: Any) -> str:
        self.calls.append(("execute", query, args))
        return "INSERT 0 1"


async def test_maps_student_profile_and_locks_it_for_the_transaction() -> None:
    connection = FakeConnection(
        fetchrow_result={"id": STUDENT_ID, "profile_status": "active"},
    )

    record = await GeofenceRepository().lock_student_profile_for_user(
        connection,
        USER_ID,
    )

    assert record is not None
    assert record.id == STUDENT_ID
    assert record.profile_status == "active"
    _, query, args = connection.calls[0]
    assert "academic.student_profiles" in query
    assert "FOR SHARE" in query
    assert args == (USER_ID,)


async def test_maps_session_state_and_check_in_window() -> None:
    connection = FakeConnection(
        fetchrow_result={
            "id": SESSION_ID,
            "status": "active",
            "check_in_opens_at": CURRENT_TIME,
            "check_in_closes_at": CURRENT_TIME,
            "requires_geofence": True,
            "requires_face_verification": True,
            "closed_at": None,
            "cancelled_at": None,
        },
    )

    record = await GeofenceRepository().lock_attendance_session(
        connection,
        SESSION_ID,
    )

    assert record is not None
    assert record.id == SESSION_ID
    assert record.requires_geofence is True
    assert record.requires_face_verification is True
    _, query, _ = connection.calls[0]
    assert "attendance_session.sessions" in query
    assert "FOR SHARE" in query


async def test_eligibility_is_derived_from_session_students() -> None:
    eligible_connection = FakeConnection(fetchrow_result={"id": UUID(int=1)})
    missing_connection = FakeConnection(fetchrow_result=None)
    repository = GeofenceRepository()

    assert await repository.lock_student_eligibility(
        eligible_connection,
        SESSION_ID,
        STUDENT_ID,
    )
    assert not await repository.lock_student_eligibility(
        missing_connection,
        SESSION_ID,
        STUDENT_ID,
    )

    _, query, args = eligible_connection.calls[0]
    assert "attendance_session.session_students" in query
    assert "FOR SHARE" in query
    assert args == (SESSION_ID, STUDENT_ID)


async def test_loads_only_the_frozen_session_geofence_snapshot() -> None:
    connection = FakeConnection(
        fetchrow_result={
            "centre_latitude": Decimal("6.795132"),
            "centre_longitude": Decimal("79.900421"),
            "radius_m": Decimal("60"),
            "accuracy_buffer_m": Decimal("10"),
            "maximum_allowed_accuracy_m": Decimal("50"),
        },
    )

    record = await GeofenceRepository().lock_session_geofence(
        connection,
        SESSION_ID,
    )

    assert record is not None
    assert record.centre_latitude == Decimal("6.795132")
    assert record.radius_m == Decimal("60")
    _, query, args = connection.calls[0]
    assert "attendance_session.session_geofences" in query
    assert "academic.classrooms" not in query
    assert "FOR SHARE" in query
    assert args == (SESSION_ID,)


async def test_overall_attempt_upsert_uses_the_unique_session_student_key() -> None:
    connection = FakeConnection(
        fetchrow_result={
            "id": VERIFICATION_ATTEMPT_ID,
            "status": IN_PROGRESS_STATUS,
            "failure_reason": None,
        },
    )

    record = await GeofenceRepository().lock_or_create_verification_attempt(
        connection,
        VERIFICATION_ATTEMPT_ID,
        SESSION_ID,
        STUDENT_ID,
        CURRENT_TIME,
    )

    assert record.id == VERIFICATION_ATTEMPT_ID
    assert record.status == IN_PROGRESS_STATUS
    _, query, args = connection.calls[0]
    assert "ON CONFLICT (session_id, student_id) DO UPDATE" in query
    assert "RETURNING id, status, failure_reason" in query
    assert args == (
        VERIFICATION_ATTEMPT_ID,
        SESSION_ID,
        STUDENT_ID,
        IN_PROGRESS_STATUS,
        CURRENT_TIME,
    )


async def test_next_attempt_number_is_allocated_from_stored_attempts() -> None:
    connection = FakeConnection(fetchval_result=3)

    attempt_number = await GeofenceRepository().next_geofence_attempt_number(
        connection,
        VERIFICATION_ATTEMPT_ID,
    )

    assert attempt_number == 3
    _, query, args = connection.calls[0]
    assert "MAX(attempt_number)" in query
    assert args == (VERIFICATION_ATTEMPT_ID,)


async def test_persistence_stores_derived_values_but_not_exact_coordinates() -> None:
    connection = FakeConnection()
    result = GeofenceValidationResult(
        decision=GeofenceDecision.RETRY_REQUIRED,
        distance_m=66.0,
        allowed_radius_m=70.0,
        next_step=GeofenceNextStep.RETRY_LOCATION,
        reason=GeofenceReason.NEAR_GEOFENCE_BOUNDARY,
    )

    await GeofenceRepository().insert_geofence_attempt(
        connection,
        GEOFENCE_ATTEMPT_ID,
        VERIFICATION_ATTEMPT_ID,
        2,
        18.5,
        result,
        CURRENT_TIME,
        CURRENT_TIME,
    )

    _, query, args = connection.calls[0]
    assert "distance_from_centre_m" in query
    assert "validation_status" in query
    assert "latitude" not in query
    assert "longitude" not in query
    assert args == (
        GEOFENCE_ATTEMPT_ID,
        VERIFICATION_ATTEMPT_ID,
        2,
        Decimal("18.5"),
        Decimal("66.0"),
        "retry_required",
        GeofenceReason.NEAR_GEOFENCE_BOUNDARY.value,
        CURRENT_TIME,
        CURRENT_TIME,
    )


async def test_terminal_failure_updates_the_overall_attempt() -> None:
    connection = FakeConnection()

    await GeofenceRepository().mark_verification_attempt_failed(
        connection,
        VERIFICATION_ATTEMPT_ID,
        GeofenceReason.OUTSIDE_GEOFENCE.value,
        CURRENT_TIME,
    )

    _, query, args = connection.calls[0]
    assert "UPDATE attendance_verification.verification_attempts" in query
    assert "completed_at" in query
    assert args == (
        VERIFICATION_ATTEMPT_ID,
        "failed",
        GeofenceReason.OUTSIDE_GEOFENCE.value,
        CURRENT_TIME,
    )
