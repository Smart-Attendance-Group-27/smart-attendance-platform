from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

import asyncpg


@dataclass(frozen=True)
class BuildingRecord:
    id: UUID
    building_name: str | None
    status: str | None


@dataclass(frozen=True)
class ClassroomRecord:
    id: UUID
    building_id: UUID
    building_name: str | None
    classroom_code: str | None
    floor_number: int | None
    capacity: int | None
    latitude: Decimal | None
    longitude: Decimal | None
    default_geofence_radius_m: Decimal | None
    status: str | None
    assigned_courses_count: int
    created_at: datetime
    updated_at: datetime


_CLASSROOM_COLUMNS = """
    classroom.id,
    classroom.building_id,
    building.building_name,
    classroom.classroom_code,
    classroom.floor_number,
    classroom.capacity,
    classroom.latitude,
    classroom.longitude,
    classroom.default_geofence_radius_m,
    classroom.status,
    (
        SELECT COUNT(DISTINCT entry.course_offering_id)
        FROM academic.timetable_entries AS entry
        WHERE entry.classroom_id = classroom.id AND entry.status = 'active'
    ) AS assigned_courses_count,
    classroom.created_at,
    classroom.updated_at
"""

_CLASSROOM_JOINS = """
    FROM academic.classrooms AS classroom
    JOIN academic.buildings AS building
        ON building.id = classroom.building_id
"""


def _row_to_classroom(row: asyncpg.Record) -> ClassroomRecord:
    return ClassroomRecord(
        id=row["id"],
        building_id=row["building_id"],
        building_name=row["building_name"],
        classroom_code=row["classroom_code"],
        floor_number=row["floor_number"],
        capacity=row["capacity"],
        latitude=row["latitude"],
        longitude=row["longitude"],
        default_geofence_radius_m=row["default_geofence_radius_m"],
        status=row["status"],
        assigned_courses_count=row["assigned_courses_count"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class AdminClassroomRepository:
    async def list_buildings(self, connection: asyncpg.Connection) -> list[BuildingRecord]:
        rows = await connection.fetch(
            """
            SELECT id, building_name, status
            FROM academic.buildings
            ORDER BY building_name ASC
            """,
        )
        return [
            BuildingRecord(id=row["id"], building_name=row["building_name"], status=row["status"])
            for row in rows
        ]

    async def building_exists(self, connection: asyncpg.Connection, building_id: UUID) -> bool:
        row = await connection.fetchrow(
            "SELECT 1 FROM academic.buildings WHERE id = $1",
            building_id,
        )
        return row is not None

    async def list_classrooms(self, connection: asyncpg.Connection) -> list[ClassroomRecord]:
        rows = await connection.fetch(
            f"""
            SELECT {_CLASSROOM_COLUMNS}
            {_CLASSROOM_JOINS}
            ORDER BY building.building_name ASC, classroom.classroom_code ASC
            """,
        )
        return [_row_to_classroom(row) for row in rows]

    async def find_classroom(
        self,
        connection: asyncpg.Connection,
        classroom_id: UUID,
        *,
        lock_for_update: bool = False,
    ) -> ClassroomRecord | None:
        lock_clause = "FOR UPDATE OF classroom" if lock_for_update else ""
        row = await connection.fetchrow(
            f"""
            SELECT {_CLASSROOM_COLUMNS}
            {_CLASSROOM_JOINS}
            WHERE classroom.id = $1
            {lock_clause}
            """,
            classroom_id,
        )
        if row is None:
            return None
        return _row_to_classroom(row)

    async def create_classroom(
        self,
        connection: asyncpg.Connection,
        *,
        classroom_id: UUID,
        building_id: UUID,
        classroom_code: str,
        floor_number: int | None,
        capacity: int | None,
        latitude: Decimal,
        longitude: Decimal,
        default_geofence_radius_m: Decimal,
        status: str,
    ) -> None:
        await connection.execute(
            """
            INSERT INTO academic.classrooms (
                id, building_id, classroom_code, floor_number, capacity,
                latitude, longitude, default_geofence_radius_m, status,
                created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, now(), now())
            """,
            classroom_id,
            building_id,
            classroom_code,
            floor_number,
            capacity,
            latitude,
            longitude,
            default_geofence_radius_m,
            status,
        )

    async def update_classroom(
        self,
        connection: asyncpg.Connection,
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
    ) -> bool:
        result = await connection.execute(
            """
            UPDATE academic.classrooms
            SET building_id = $2,
                classroom_code = $3,
                floor_number = $4,
                capacity = $5,
                latitude = $6,
                longitude = $7,
                default_geofence_radius_m = $8,
                status = $9,
                updated_at = now()
            WHERE id = $1
            """,
            classroom_id,
            building_id,
            classroom_code,
            floor_number,
            capacity,
            latitude,
            longitude,
            default_geofence_radius_m,
            status,
        )
        return result == "UPDATE 1"
