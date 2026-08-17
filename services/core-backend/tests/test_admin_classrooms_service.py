from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from modules.academic.admin_classrooms.exception import (
    BuildingNotFoundError,
    ClassroomNotFoundError,
)
from modules.academic.admin_classrooms.repository import ClassroomRecord
from modules.academic.admin_classrooms.service import AdminClassroomService

ACTOR_ID = UUID("20000000-0000-0000-0000-000000000001")
CLASSROOM_ID = UUID("33000000-0000-0000-0000-000000000001")
BUILDING_ID = UUID("32000000-0000-0000-0000-000000000001")
CURRENT_TIME = datetime(2026, 8, 13, 5, 30, tzinfo=UTC)


class FakeTransaction:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeConnection:
    def __init__(self) -> None:
        self.executed_queries: list[str] = []
        self.executed_args: list[tuple] = []

    def transaction(self) -> FakeTransaction:
        return FakeTransaction()

    async def execute(self, query: str, *args) -> None:
        self.executed_queries.append(query)
        self.executed_args.append(args)


class FakeAcquire:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self.connection

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakePool:
    def __init__(self) -> None:
        self.connection = FakeConnection()

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.connection)


def build_classroom(**overrides) -> ClassroomRecord:
    defaults = dict(
        id=CLASSROOM_ID,
        building_id=BUILDING_ID,
        building_name="Engineering Faculty Building",
        classroom_code="LH-02",
        floor_number=1,
        capacity=120,
        latitude=Decimal("6.7961"),
        longitude=Decimal("79.9007"),
        default_geofence_radius_m=Decimal("40"),
        status="active",
        assigned_courses_count=1,
        created_at=CURRENT_TIME,
        updated_at=CURRENT_TIME,
    )
    defaults.update(overrides)
    return ClassroomRecord(**defaults)


class FakeAdminClassroomRepository:
    def __init__(self, *, classroom: ClassroomRecord | None, building_exists: bool = True) -> None:
        self.classroom = classroom
        self.building_exists_value = building_exists
        self.find_classroom_calls: list[bool] = []
        self.updated_existing = classroom is not None

    async def find_classroom(self, connection, classroom_id, *, lock_for_update: bool = False):
        self.find_classroom_calls.append(lock_for_update)
        return self.classroom

    async def building_exists(self, connection, building_id) -> bool:
        return self.building_exists_value

    async def update_classroom(self, connection, classroom_id, **kwargs) -> bool:
        return self.updated_existing

    async def create_classroom(self, connection, **kwargs) -> None:
        pass


WRITE_KWARGS = dict(
    building_id=BUILDING_ID,
    classroom_code="LH-02",
    floor_number=2,
    capacity=100,
    latitude=Decimal("6.8"),
    longitude=Decimal("79.9"),
    default_geofence_radius_m=Decimal("30"),
    status="active",
)


async def test_update_classroom_locks_the_row_before_mutating() -> None:
    repository = FakeAdminClassroomRepository(classroom=build_classroom())
    service = AdminClassroomService(repository=repository)

    await service.update_classroom(FakePool(), ACTOR_ID, CLASSROOM_ID, **WRITE_KWARGS)

    # The pre-update lookup (to snapshot "before" and check existence) must be
    # a locking read — otherwise two concurrent edits could both read the same
    # starting state and the audit log's old_values would go stale.
    assert repository.find_classroom_calls[0] is True


async def test_update_classroom_writes_an_audit_log_entry() -> None:
    repository = FakeAdminClassroomRepository(classroom=build_classroom())
    service = AdminClassroomService(repository=repository)
    pool = FakePool()

    await service.update_classroom(pool, ACTOR_ID, CLASSROOM_ID, **WRITE_KWARGS)

    audit_query = pool.connection.executed_queries[0]
    audit_args = pool.connection.executed_args[0]
    assert "audit.audit_logs" in audit_query
    assert audit_args[0] == ACTOR_ID
    assert audit_args[1] == "administrator"
    assert audit_args[2] == "classroom.update"
    assert audit_args[4] == CLASSROOM_ID


async def test_update_classroom_rejects_missing_classroom() -> None:
    repository = FakeAdminClassroomRepository(classroom=None)
    service = AdminClassroomService(repository=repository)

    with pytest.raises(ClassroomNotFoundError):
        await service.update_classroom(FakePool(), ACTOR_ID, CLASSROOM_ID, **WRITE_KWARGS)


async def test_update_classroom_rejects_missing_building() -> None:
    repository = FakeAdminClassroomRepository(classroom=build_classroom(), building_exists=False)
    service = AdminClassroomService(repository=repository)

    with pytest.raises(BuildingNotFoundError):
        await service.update_classroom(FakePool(), ACTOR_ID, CLASSROOM_ID, **WRITE_KWARGS)


async def test_create_classroom_writes_an_audit_log_entry() -> None:
    repository = FakeAdminClassroomRepository(classroom=build_classroom())
    service = AdminClassroomService(repository=repository)
    pool = FakePool()

    await service.create_classroom(
        pool,
        ACTOR_ID,
        building_id=BUILDING_ID,
        classroom_code="LH-05",
        floor_number=3,
        capacity=60,
        latitude=Decimal("6.8"),
        longitude=Decimal("79.9"),
        default_geofence_radius_m=Decimal("25"),
        status="active",
    )

    audit_query = pool.connection.executed_queries[0]
    audit_args = pool.connection.executed_args[0]
    assert "audit.audit_logs" in audit_query
    assert audit_args[2] == "classroom.create"


async def test_create_classroom_rejects_missing_building() -> None:
    repository = FakeAdminClassroomRepository(classroom=build_classroom(), building_exists=False)
    service = AdminClassroomService(repository=repository)

    with pytest.raises(BuildingNotFoundError):
        await service.create_classroom(
            FakePool(),
            ACTOR_ID,
            building_id=BUILDING_ID,
            classroom_code="LH-05",
            floor_number=3,
            capacity=60,
            latitude=Decimal("6.8"),
            longitude=Decimal("79.9"),
            default_geofence_radius_m=Decimal("25"),
            status="active",
        )
