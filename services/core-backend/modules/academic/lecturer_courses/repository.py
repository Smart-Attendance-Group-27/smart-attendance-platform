from dataclasses import dataclass
from datetime import time
from decimal import Decimal
from uuid import UUID

import asyncpg


@dataclass(frozen=True)
class LecturerCourseRecord:
    course_offering_id: UUID
    course_code: str | None
    course_name: str | None
    department_name: str | None
    course_type: str | None
    status: str | None
    enrolled_count: int
    attendance_rate_percent: Decimal | None


@dataclass(frozen=True)
class LecturerTimetableEntryRecord:
    id: UUID
    course_code: str | None
    course_name: str | None
    day_of_week: int
    start_time: time
    end_time: time
    classroom_code: str | None
    building_name: str | None


class LecturerCourseRepository:
    async def list_courses_for_lecturer(
        self,
        connection: asyncpg.Connection,
        lecturer_id: UUID,
    ) -> list[LecturerCourseRecord]:
        rows = await connection.fetch(
            """
            SELECT
                offering.id AS course_offering_id,
                course.course_code,
                course.course_name,
                department.department_name,
                offering.course_type,
                offering.status,
                (
                    SELECT COUNT(*)
                    FROM academic.course_enrolments AS enrolment
                    WHERE enrolment.course_offering_id = offering.id
                      AND enrolment.enrolment_status = 'enrolled'
                ) AS enrolled_count,
                (
                    SELECT
                        CASE WHEN COUNT(*) = 0 THEN NULL
                        ELSE ROUND(
                            100.0 * COUNT(*) FILTER (
                                WHERE record.attendance_status IN ('present', 'late')
                            ) / COUNT(*),
                            1
                        )
                        END
                    FROM attendance_verification.attendance_records AS record
                    JOIN attendance_session.sessions AS session
                        ON session.id = record.session_id
                    WHERE session.course_offering_id = offering.id
                ) AS attendance_rate_percent
            FROM academic.course_lecturers AS assignment
            JOIN academic.course_offerings AS offering
                ON offering.id = assignment.course_offering_id
            JOIN academic.courses AS course
                ON course.id = offering.course_id
            LEFT JOIN academic.departments AS department
                ON department.id = course.department_id
            WHERE assignment.lecturer_id = $1
            ORDER BY course.course_code ASC
            """,
            lecturer_id,
        )

        return [
            LecturerCourseRecord(
                course_offering_id=row["course_offering_id"],
                course_code=row["course_code"],
                course_name=row["course_name"],
                department_name=row["department_name"],
                course_type=row["course_type"],
                status=row["status"],
                enrolled_count=row["enrolled_count"],
                attendance_rate_percent=row["attendance_rate_percent"],
            )
            for row in rows
        ]

    async def list_timetable_for_lecturer(
        self,
        connection: asyncpg.Connection,
        lecturer_id: UUID,
    ) -> list[LecturerTimetableEntryRecord]:
        rows = await connection.fetch(
            """
            SELECT
                entry.id,
                course.course_code,
                course.course_name,
                entry.day_of_week,
                entry.start_time,
                entry.end_time,
                classroom.classroom_code,
                building.building_name
            FROM academic.course_lecturers AS assignment
            JOIN academic.course_offerings AS offering
                ON offering.id = assignment.course_offering_id
            JOIN academic.courses AS course
                ON course.id = offering.course_id
            JOIN academic.timetable_entries AS entry
                ON entry.course_offering_id = offering.id
            LEFT JOIN academic.classrooms AS classroom
                ON classroom.id = entry.classroom_id
            LEFT JOIN academic.buildings AS building
                ON building.id = classroom.building_id
            WHERE assignment.lecturer_id = $1
              AND entry.status = 'active'
            ORDER BY entry.day_of_week ASC, entry.start_time ASC
            """,
            lecturer_id,
        )

        return [
            LecturerTimetableEntryRecord(
                id=row["id"],
                course_code=row["course_code"],
                course_name=row["course_name"],
                day_of_week=row["day_of_week"],
                start_time=row["start_time"],
                end_time=row["end_time"],
                classroom_code=row["classroom_code"],
                building_name=row["building_name"],
            )
            for row in rows
        ]
