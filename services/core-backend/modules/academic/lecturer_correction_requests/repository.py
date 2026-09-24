from dataclasses import dataclass
from uuid import UUID

import asyncpg


@dataclass(frozen=True)
class CorrectionRequestRecord:
    id: UUID
    request_type: str
    category: str
    course_offering_id: UUID
    timetable_entry_id: UUID | None
    status: str


class CorrectionRequestRepository:
    async def is_offering_assigned(
        self,
        connection: asyncpg.Connection,
        lecturer_id: UUID,
        course_offering_id: UUID,
    ) -> bool:
        row = await connection.fetchrow(
            """
            SELECT 1
            FROM academic.course_lecturers
            WHERE lecturer_id = $1 AND course_offering_id = $2
            """,
            lecturer_id,
            course_offering_id,
        )
        return row is not None

    async def find_assigned_timetable_offering(
        self,
        connection: asyncpg.Connection,
        lecturer_id: UUID,
        timetable_entry_id: UUID,
    ) -> UUID | None:
        row = await connection.fetchrow(
            """
            SELECT entry.course_offering_id
            FROM academic.timetable_entries AS entry
            JOIN academic.course_lecturers AS assignment
                ON assignment.course_offering_id = entry.course_offering_id
            WHERE entry.id = $2 AND assignment.lecturer_id = $1
            """,
            lecturer_id,
            timetable_entry_id,
        )
        return row["course_offering_id"] if row is not None else None

    async def insert(
        self,
        connection: asyncpg.Connection,
        *,
        request_id: UUID,
        requested_by: UUID,
        request_type: str,
        course_offering_id: UUID,
        timetable_entry_id: UUID | None,
        category: str,
        description: str,
    ) -> CorrectionRequestRecord:
        row = await connection.fetchrow(
            """
            INSERT INTO academic.correction_requests (
                id, requested_by, request_type, course_offering_id,
                timetable_entry_id, category, description
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id, request_type, category, course_offering_id,
                      timetable_entry_id, status
            """,
            request_id,
            requested_by,
            request_type,
            course_offering_id,
            timetable_entry_id,
            category,
            description,
        )
        return CorrectionRequestRecord(
            id=row["id"],
            request_type=row["request_type"],
            category=row["category"],
            course_offering_id=row["course_offering_id"],
            timetable_entry_id=row["timetable_entry_id"],
            status=row["status"],
        )
