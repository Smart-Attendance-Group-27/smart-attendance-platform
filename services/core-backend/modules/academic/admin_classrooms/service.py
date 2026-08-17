from decimal import Decimal
from uuid import UUID, uuid4

import asyncpg

from modules.academic.admin_classrooms.exception import (
    BuildingNotFoundError,
    ClassroomNotFoundError,
)
from modules.academic.admin_classrooms.repository import (
    AdminClassroomRepository,
    BuildingRecord,
    ClassroomRecord,
)
from modules.audit.repository import write_audit_log

ACTOR_TYPE_ADMINISTRATOR = "administrator"
AUDIT_ENTITY_TYPE = "classroom"


class AdminClassroomService:
    def __init__(self, repository: AdminClassroomRepository | None = None) -> None:
        self._repository = repository or AdminClassroomRepository()

    async def list_buildings(self, pool: asyncpg.Pool) -> list[BuildingRecord]:
        async with pool.acquire() as connection:
            return await self._repository.list_buildings(connection)

    async def list_classrooms(self, pool: asyncpg.Pool) -> list[ClassroomRecord]:
        async with pool.acquire() as connection:
            return await self._repository.list_classrooms(connection)

    async def get_classroom(self, pool: asyncpg.Pool, classroom_id: UUID) -> ClassroomRecord:
        async with pool.acquire() as connection:
            classroom = await self._repository.find_classroom(connection, classroom_id)
        if classroom is None:
            raise ClassroomNotFoundError()
        return classroom

    async def create_classroom(
        self,
        pool: asyncpg.Pool,
        actor_user_id: UUID,
        *,
        building_id: UUID,
        classroom_code: str,
        floor_number: int | None,
        capacity: int | None,
        latitude: Decimal,
        longitude: Decimal,
        default_geofence_radius_m: Decimal,
        status: str,
    ) -> ClassroomRecord:
        classroom_id = uuid4()
        async with pool.acquire() as connection, connection.transaction():
            if not await self._repository.building_exists(connection, building_id):
                raise BuildingNotFoundError()

            await self._repository.create_classroom(
                connection,
                classroom_id=classroom_id,
                building_id=building_id,
                classroom_code=classroom_code,
                floor_number=floor_number,
                capacity=capacity,
                latitude=latitude,
                longitude=longitude,
                default_geofence_radius_m=default_geofence_radius_m,
                status=status,
            )
            created = await self._repository.find_classroom(connection, classroom_id)
            assert created is not None

            await write_audit_log(
                connection,
                actor_user_id=actor_user_id,
                actor_type=ACTOR_TYPE_ADMINISTRATOR,
                action="classroom.create",
                entity_type=AUDIT_ENTITY_TYPE,
                entity_id=classroom_id,
                old_values=None,
                new_values=_snapshot(created),
            )

        return created

    async def update_classroom(
        self,
        pool: asyncpg.Pool,
        actor_user_id: UUID,
        classroom_id: UUID,
        *,
        building_id: UUID,
        classroom_code: str,
        floor_number: int | None,
        capacity: int | None,
        latitude: Decimal,
        longitude: Decimal,
        default_geofence_radius_m: Decimal,
        status: str,
    ) -> ClassroomRecord:
        async with pool.acquire() as connection, connection.transaction():
            before = await self._repository.find_classroom(connection, classroom_id)
            if before is None:
                raise ClassroomNotFoundError()
            if not await self._repository.building_exists(connection, building_id):
                raise BuildingNotFoundError()

            updated_existing = await self._repository.update_classroom(
                connection,
                classroom_id,
                building_id=building_id,
                classroom_code=classroom_code,
                floor_number=floor_number,
                capacity=capacity,
                latitude=latitude,
                longitude=longitude,
                default_geofence_radius_m=default_geofence_radius_m,
                status=status,
            )
            if not updated_existing:
                raise ClassroomNotFoundError()

            after = await self._repository.find_classroom(connection, classroom_id)
            assert after is not None

            await write_audit_log(
                connection,
                actor_user_id=actor_user_id,
                actor_type=ACTOR_TYPE_ADMINISTRATOR,
                action="classroom.update",
                entity_type=AUDIT_ENTITY_TYPE,
                entity_id=classroom_id,
                old_values=_snapshot(before),
                new_values=_snapshot(after),
            )

        return after


def _snapshot(record: ClassroomRecord) -> dict:
    return {
        "buildingId": str(record.building_id),
        "classroomCode": record.classroom_code,
        "floorNumber": record.floor_number,
        "capacity": record.capacity,
        "latitude": float(record.latitude) if record.latitude is not None else None,
        "longitude": float(record.longitude) if record.longitude is not None else None,
        "defaultGeofenceRadiusM": (
            float(record.default_geofence_radius_m)
            if record.default_geofence_radius_m is not None
            else None
        ),
        "status": record.status,
    }
