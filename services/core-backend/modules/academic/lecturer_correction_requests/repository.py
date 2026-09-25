from dataclasses import dataclass
from datetime import datetime, time
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


@dataclass(frozen=True)
class OwnCorrectionRequestRecord:
    id: UUID
    request_type: str
    category: str
    course_code: str | None
    course_name: str | None
    timetable_day_of_week: int | None
    timetable_start_time: time | None
    timetable_end_time: time | None
    timetable_classroom_code: str | None
    description: str
    status: str
    review_note: str | None
    created_at: datetime
    reviewed_at: datetime | None


class CorrectionRequestRepository:
    async def list_for_requester(
        self,
        connection: asyncpg.Connection,
        requested_by: UUID,
        limit: int = 100,
    ) -> list[OwnCorrectionRequestRecord]:
        rows = await connection.fetch(
            """
            SELECT
                request.id, request.request_type, request.category,
                course.course_code, course.course_name,
                entry.day_of_week, entry.start_time, entry.end_time,
                classroom.classroom_code,
                request.description, request.status, request.review_note,
                request.created_at, request.reviewed_at
            FROM academic.correction_requests AS request
            JOIN academic.course_offerings AS offering
                ON offering.id = request.course_offering_id
            JOIN academic.courses AS course
                ON course.id = offering.course_id
            LEFT JOIN academic.timetable_entries AS entry
                ON entry.id = request.timetable_entry_id
            LEFT JOIN academic.classrooms AS classroom
                ON classroom.id = entry.classroom_id
            WHERE request.requested_by = $1
            ORDER BY request.created_at DESC
            LIMIT $2
            """,
            requested_by,
            limit,
        )
        return [
            OwnCorrectionRequestRecord(
                id=row["id"],
                request_type=row["request_type"],
                category=row["category"],
                course_code=row["course_code"],
                course_name=row["course_name"],
                timetable_day_of_week=row["day_of_week"],
                timetable_start_time=row["start_time"],
                timetable_end_time=row["end_time"],
                timetable_classroom_code=row["classroom_code"],
                description=row["description"],
                status=row["status"],
                review_note=row["review_note"],
                created_at=row["created_at"],
                reviewed_at=row["reviewed_at"],
            )
            for row in rows
        ]

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
