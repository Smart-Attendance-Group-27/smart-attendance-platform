from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import asyncpg


@dataclass(frozen=True)
class StudentCourseRecord:
    course_offering_id: UUID
    course_code: str | None
    course_name: str | None
    lecturers: str | None
    semester_number: int | None
    academic_year_start: date | datetime | None
    attended_sessions: int
    total_sessions: int
    attendance_percentage: Decimal | None


@dataclass(frozen=True)
class StudentCourseSessionRecord:
    id: UUID
    course_offering_id: UUID
    session_title: str | None
    session_type: str | None
    scheduled_start_at: datetime
    scheduled_end_at: datetime
    check_in_opens_at: datetime | None
    check_in_closes_at: datetime | None
    venue: str | None
    status: str | None
    closed_at: datetime | None
    cancelled_at: datetime | None
    attendance_status: str | None
    attendance_recorded_at: datetime | None


@dataclass(frozen=True)
class StudentAttendanceRecord:
    id: UUID
    course_offering_id: UUID
    session_title: str | None
    attendance_status: str | None
    created_at: datetime | None


class StudentCourseRepository:
    async def list_courses_for_student(
        self,
        connection: asyncpg.Connection,
        student_id: UUID,
    ) -> list[StudentCourseRecord]:
        rows = await connection.fetch(
            """
            SELECT
                offering.id AS course_offering_id,
                course.course_code,
                course.course_name,
                NULLIF(
                    string_agg(
                        DISTINCT trim(
                            concat_ws(
                                ' ',
                                lecturer.first_name,
                                lecturer.middle_name,
                                lecturer.last_name
                            )
                        ),
                        ', '
                    ),
                    ''
                ) AS lecturers,
                semester.semester_number,
                academic_year.start_date AS academic_year_start,
                COUNT(DISTINCT session.id) FILTER (
                    WHERE record.attendance_status IN ('present', 'late')
                ) AS attended_sessions,
                COUNT(DISTINCT session.id) FILTER (
                    WHERE session.scheduled_end_at <= now()
                       OR record.id IS NOT NULL
                ) AS total_sessions,
                CASE
                    WHEN COUNT(DISTINCT session.id) FILTER (
                        WHERE session.scheduled_end_at <= now()
                           OR record.id IS NOT NULL
                    ) = 0 THEN NULL
                    ELSE ROUND(
                        100.0 * COUNT(DISTINCT session.id) FILTER (
                            WHERE record.attendance_status IN ('present', 'late')
                        ) / COUNT(DISTINCT session.id) FILTER (
                            WHERE session.scheduled_end_at <= now()
                               OR record.id IS NOT NULL
                        ),
                        1
                    )
                END AS attendance_percentage
            FROM academic.course_enrolments AS enrolment
            JOIN academic.course_offerings AS offering
                ON offering.id = enrolment.course_offering_id
            JOIN academic.courses AS course
                ON course.id = offering.course_id
            LEFT JOIN academic.semesters AS semester
                ON semester.id = offering.semester_id
            LEFT JOIN academic.academic_years AS academic_year
                ON academic_year.id = semester.academic_year_id
            LEFT JOIN academic.course_lecturers AS assignment
                ON assignment.course_offering_id = offering.id
            LEFT JOIN academic.lecturer_profiles AS lecturer
                ON lecturer.id = assignment.lecturer_id
            LEFT JOIN attendance_session.sessions AS session
                ON session.course_offering_id = offering.id
            LEFT JOIN attendance_verification.attendance_records AS record
                ON record.session_id = session.id
               AND record.student_id = enrolment.student_id
            WHERE enrolment.student_id = $1
              AND enrolment.enrolment_status = 'enrolled'
              AND offering.status = 'active'
            GROUP BY
                offering.id,
                course.course_code,
                course.course_name,
                semester.semester_number,
                academic_year.start_date
            ORDER BY course.course_code ASC
            """,
            student_id,
        )

        return [
            StudentCourseRecord(
                course_offering_id=row["course_offering_id"],
                course_code=row["course_code"],
                course_name=row["course_name"],
                lecturers=row["lecturers"],
                semester_number=row["semester_number"],
                academic_year_start=row["academic_year_start"],
                attended_sessions=row["attended_sessions"],
                total_sessions=row["total_sessions"],
                attendance_percentage=row["attendance_percentage"],
            )
            for row in rows
        ]

    async def list_sessions_for_student_courses(
        self,
        connection: asyncpg.Connection,
        student_id: UUID,
    ) -> list[StudentCourseSessionRecord]:
        rows = await connection.fetch(
            """
            SELECT
                session.id,
                session.course_offering_id,
                session.session_title,
                session.session_type,
                session.scheduled_start_at,
                session.scheduled_end_at,
                session.check_in_opens_at,
                session.check_in_closes_at,
                COALESCE(
                    exception_classroom.classroom_code,
                    timetable_classroom.classroom_code
                ) AS venue,
                session.status,
                session.closed_at,
                session.cancelled_at,
                record.attendance_status,
                record.created_at AS attendance_recorded_at
            FROM academic.course_enrolments AS enrolment
            JOIN attendance_session.sessions AS session
                ON session.course_offering_id = enrolment.course_offering_id
            LEFT JOIN academic.timetable_entries AS timetable
                ON timetable.id = session.timetable_entry_id
            LEFT JOIN academic.classrooms AS timetable_classroom
                ON timetable_classroom.id = timetable.classroom_id
            LEFT JOIN academic.timetable_exceptions AS timetable_exception
                ON timetable_exception.id = session.timetable_exception_id
            LEFT JOIN academic.classrooms AS exception_classroom
                ON exception_classroom.id = timetable_exception.new_classroom_id
            LEFT JOIN attendance_verification.attendance_records AS record
                ON record.session_id = session.id
               AND record.student_id = enrolment.student_id
            WHERE enrolment.student_id = $1
              AND enrolment.enrolment_status = 'enrolled'
            ORDER BY session.scheduled_start_at DESC, session.id ASC
            """,
            student_id,
        )

        return [
            StudentCourseSessionRecord(
                id=row["id"],
                course_offering_id=row["course_offering_id"],
                session_title=row["session_title"],
                session_type=row["session_type"],
                scheduled_start_at=row["scheduled_start_at"],
                scheduled_end_at=row["scheduled_end_at"],
                check_in_opens_at=row["check_in_opens_at"],
                check_in_closes_at=row["check_in_closes_at"],
                venue=row["venue"],
                status=row["status"],
                closed_at=row["closed_at"],
                cancelled_at=row["cancelled_at"],
                attendance_status=row["attendance_status"],
                attendance_recorded_at=row["attendance_recorded_at"],
            )
            for row in rows
        ]

    async def list_attendance_records_for_student_courses(
        self,
        connection: asyncpg.Connection,
        student_id: UUID,
    ) -> list[StudentAttendanceRecord]:
        rows = await connection.fetch(
            """
            SELECT
                record.id,
                session.course_offering_id,
                session.session_title,
                record.attendance_status,
                record.created_at
            FROM attendance_verification.attendance_records AS record
            JOIN attendance_session.sessions AS session
                ON session.id = record.session_id
            JOIN academic.course_enrolments AS enrolment
                ON enrolment.course_offering_id = session.course_offering_id
               AND enrolment.student_id = record.student_id
            WHERE record.student_id = $1
              AND enrolment.enrolment_status = 'enrolled'
            ORDER BY record.created_at DESC, record.id ASC
            """,
            student_id,
        )

        return [
            StudentAttendanceRecord(
                id=row["id"],
                course_offering_id=row["course_offering_id"],
                session_title=row["session_title"],
                attendance_status=row["attendance_status"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
