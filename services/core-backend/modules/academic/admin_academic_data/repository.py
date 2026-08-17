from dataclasses import dataclass
from datetime import time
from decimal import Decimal
from uuid import UUID

import asyncpg


@dataclass(frozen=True)
class AdminCourseRecord:
    id: UUID
    course_code: str | None
    course_name: str | None
    department_name: str | None
    credits: Decimal | None
    status: str | None


@dataclass(frozen=True)
class AdminCourseOfferingRecord:
    id: UUID
    course_code: str | None
    course_name: str | None
    semester_label: str
    batch_year: int | None
    course_type: str | None
    attendance_threshold_percent: Decimal | None
    enrolled_count: int
    status: str | None


@dataclass(frozen=True)
class AdminTimetableEntryRecord:
    id: UUID
    course_code: str | None
    course_name: str | None
    day_of_week: int
    start_time: time
    end_time: time
    classroom_code: str | None
    lecturer_name: str | None


@dataclass(frozen=True)
class AdminEnrolmentRecord:
    id: UUID
    student_name: str
    registration_number: str | None
    course_code: str | None
    semester_label: str
    enrolment_status: str | None


_SEMESTER_LABEL_EXPR = """
    'Semester ' || semester.semester_number || ' (' ||
    EXTRACT(YEAR FROM academic_year.start_date) || ')'
"""


class AdminAcademicDataRepository:
    async def list_courses(self, connection: asyncpg.Connection) -> list[AdminCourseRecord]:
        rows = await connection.fetch(
            """
            SELECT
                course.id,
                course.course_code,
                course.course_name,
                department.department_name,
                course.credits,
                course.status
            FROM academic.courses AS course
            LEFT JOIN academic.departments AS department
                ON department.id = course.department_id
            ORDER BY course.course_code ASC
            """,
        )
        return [
            AdminCourseRecord(
                id=row["id"],
                course_code=row["course_code"],
                course_name=row["course_name"],
                department_name=row["department_name"],
                credits=row["credits"],
                status=row["status"],
            )
            for row in rows
        ]

    async def list_course_offerings(
        self,
        connection: asyncpg.Connection,
    ) -> list[AdminCourseOfferingRecord]:
        rows = await connection.fetch(
            f"""
            SELECT
                offering.id,
                course.course_code,
                course.course_name,
                {_SEMESTER_LABEL_EXPR} AS semester_label,
                offering.batch_year,
                offering.course_type,
                offering.attendance_threshold,
                (
                    SELECT COUNT(*) FROM academic.course_enrolments AS enrolment
                    WHERE enrolment.course_offering_id = offering.id
                      AND enrolment.enrolment_status = 'enrolled'
                ) AS enrolled_count,
                offering.status
            FROM academic.course_offerings AS offering
            JOIN academic.courses AS course
                ON course.id = offering.course_id
            JOIN academic.semesters AS semester
                ON semester.id = offering.semester_id
            JOIN academic.academic_years AS academic_year
                ON academic_year.id = semester.academic_year_id
            ORDER BY academic_year.start_date DESC, course.course_code ASC
            """,
        )
        return [
            AdminCourseOfferingRecord(
                id=row["id"],
                course_code=row["course_code"],
                course_name=row["course_name"],
                semester_label=row["semester_label"],
                batch_year=row["batch_year"],
                course_type=row["course_type"],
                attendance_threshold_percent=row["attendance_threshold"],
                enrolled_count=row["enrolled_count"],
                status=row["status"],
            )
            for row in rows
        ]

    async def list_timetable(self, connection: asyncpg.Connection) -> list[AdminTimetableEntryRecord]:
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
                lecturers.lecturer_name
            FROM academic.timetable_entries AS entry
            JOIN academic.course_offerings AS offering
                ON offering.id = entry.course_offering_id
            JOIN academic.courses AS course
                ON course.id = offering.course_id
            LEFT JOIN academic.classrooms AS classroom
                ON classroom.id = entry.classroom_id
            LEFT JOIN LATERAL (
                -- A course offering can have more than one assigned lecturer;
                -- surface all of them rather than arbitrarily picking one.
                SELECT STRING_AGG(
                    TRIM(CONCAT_WS(' ', lp.first_name, NULLIF(lp.middle_name, ''), lp.last_name)),
                    ', '
                ) AS lecturer_name
                FROM academic.course_lecturers AS assignment
                JOIN academic.lecturer_profiles AS lp
                    ON lp.id = assignment.lecturer_id
                WHERE assignment.course_offering_id = offering.id
            ) AS lecturers ON TRUE
            WHERE entry.status = 'active'
            ORDER BY entry.day_of_week ASC, entry.start_time ASC
            """,
        )
        return [
            AdminTimetableEntryRecord(
                id=row["id"],
                course_code=row["course_code"],
                course_name=row["course_name"],
                day_of_week=row["day_of_week"],
                start_time=row["start_time"],
                end_time=row["end_time"],
                classroom_code=row["classroom_code"],
                lecturer_name=row["lecturer_name"] or None,
            )
            for row in rows
        ]

    async def list_enrolments(self, connection: asyncpg.Connection) -> list[AdminEnrolmentRecord]:
        rows = await connection.fetch(
            f"""
            SELECT
                enrolment.id,
                TRIM(
                    CONCAT_WS(' ', student.first_name, NULLIF(student.middle_name, ''), student.last_name)
                ) AS student_name,
                student.registration_number,
                course.course_code,
                {_SEMESTER_LABEL_EXPR} AS semester_label,
                enrolment.enrolment_status
            FROM academic.course_enrolments AS enrolment
            JOIN academic.student_profiles AS student
                ON student.id = enrolment.student_id
            JOIN academic.course_offerings AS offering
                ON offering.id = enrolment.course_offering_id
            JOIN academic.courses AS course
                ON course.id = offering.course_id
            JOIN academic.semesters AS semester
                ON semester.id = offering.semester_id
            JOIN academic.academic_years AS academic_year
                ON academic_year.id = semester.academic_year_id
            ORDER BY enrolment.enrolled_at DESC NULLS LAST
            """,
        )
        return [
            AdminEnrolmentRecord(
                id=row["id"],
                student_name=row["student_name"] or "",
                registration_number=row["registration_number"],
                course_code=row["course_code"],
                semester_label=row["semester_label"],
                enrolment_status=row["enrolment_status"],
            )
            for row in rows
        ]
