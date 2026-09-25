from dataclasses import dataclass
from datetime import datetime, time
from uuid import UUID

import asyncpg

_SELECT = """
    SELECT
        request.id, request.request_type, request.category,
        COALESCE(
            NULLIF(TRIM(CONCAT_WS(' ', profile.first_name, profile.last_name)), ''),
            requester.email,
            ''
        ) AS requester_name,
        profile.employee_number,
        course.course_code, course.course_name,
        entry.day_of_week, entry.start_time, entry.end_time,
        classroom.classroom_code,
        request.description, request.status, request.review_note,
        request.created_at, request.reviewed_at
    FROM academic.correction_requests AS request
    JOIN identity.users AS requester
        ON requester.id = request.requested_by
    LEFT JOIN academic.lecturer_profiles AS profile
        ON profile.user_id = request.requested_by
    JOIN academic.course_offerings AS offering
        ON offering.id = request.course_offering_id
    JOIN academic.courses AS course
        ON course.id = offering.course_id
    LEFT JOIN academic.timetable_entries AS entry
        ON entry.id = request.timetable_entry_id
    LEFT JOIN academic.classrooms AS classroom
        ON classroom.id = entry.classroom_id
"""


@dataclass(frozen=True)
class AdminCorrectionRequestRecord:
    id: UUID
    request_type: str
    category: str
    requester_name: str
    requester_employee_number: str | None
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


def _to_record(row: asyncpg.Record) -> AdminCorrectionRequestRecord:
    return AdminCorrectionRequestRecord(
        id=row["id"],
        request_type=row["request_type"],
        category=row["category"],
        requester_name=row["requester_name"],
        requester_employee_number=row["employee_number"],
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


class AdminCorrectionRequestRepository:
    async def list_requests(
        self,
        connection: asyncpg.Connection,
        *,
        status: str | None,
        limit: int = 200,
    ) -> list[AdminCorrectionRequestRecord]:
        rows = await connection.fetch(
            f"""
            {_SELECT}
            WHERE ($1::text IS NULL OR request.status = $1)
            ORDER BY (request.status = 'pending') DESC, request.created_at DESC
            LIMIT $2
            """,
            status,
            limit,
        )
        return [_to_record(row) for row in rows]

    async def find_request(
        self,
        connection: asyncpg.Connection,
        request_id: UUID,
    ) -> AdminCorrectionRequestRecord | None:
        row = await connection.fetchrow(f"{_SELECT} WHERE request.id = $1", request_id)
        return _to_record(row) if row is not None else None

    async def lock_status(
        self,
        connection: asyncpg.Connection,
        request_id: UUID,
    ) -> str | None:
        row = await connection.fetchrow(
            "SELECT status FROM academic.correction_requests WHERE id = $1 FOR UPDATE",
            request_id,
        )
        return row["status"] if row is not None else None

    async def record_decision(
        self,
        connection: asyncpg.Connection,
        request_id: UUID,
        *,
        status: str,
        reviewed_by: UUID,
        review_note: str | None,
    ) -> None:
        await connection.execute(
            """
            UPDATE academic.correction_requests
            SET status = $2, reviewed_by = $3, reviewed_at = now(),
                review_note = $4, updated_at = now()
            WHERE id = $1
            """,
            request_id,
            status,
            reviewed_by,
            review_note,
        )
