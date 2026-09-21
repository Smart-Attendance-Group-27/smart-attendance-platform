from dataclasses import dataclass
from decimal import Decimal

import asyncpg

AT_RISK_THRESHOLD_PERCENT = 70
DEFAULT_TREND_WEEKS = 8


@dataclass(frozen=True)
class InstitutionSummaryRecord:
    overall_attendance_percent: Decimal | None
    total_sessions_completed: int
    total_students: int
    total_lecturers: int
    students_at_risk_count: int


@dataclass(frozen=True)
class WeeklyTrendRecord:
    week_start: object
    attendance_rate_percent: Decimal


@dataclass(frozen=True)
class FacultyAttendanceRecord:
    faculty_name: str
    attendance_rate_percent: Decimal | None


@dataclass(frozen=True)
class AtRiskCourseRecord:
    course_code: str
    course_name: str
    attendance_rate_percent: Decimal


class AdminInstitutionReportRepository:
    async def get_summary(self, connection: asyncpg.Connection) -> InstitutionSummaryRecord:
        row = await connection.fetchrow(
            """
            SELECT
                (
                    SELECT ROUND(
                        100.0 * COUNT(*) FILTER (WHERE record.attendance_status IN ('present', 'late'))
                        / NULLIF(COUNT(*), 0),
                        1
                    )
                    FROM attendance_session.sessions AS session
                    JOIN attendance_session.session_students AS roster
                        ON roster.session_id = session.id
                    LEFT JOIN attendance_verification.attendance_records AS record
                        ON record.session_id = session.id AND record.student_id = roster.student_id
                    WHERE session.closed_at IS NOT NULL AND session.cancelled_at IS NULL
                ) AS overall_attendance_percent,
                (
                    SELECT COUNT(*) FROM attendance_session.sessions
                    WHERE closed_at IS NOT NULL AND cancelled_at IS NULL
                ) AS total_sessions_completed,
                (
                    SELECT COUNT(*) FROM academic.student_profiles WHERE profile_status = 'active'
                ) AS total_students,
                (
                    SELECT COUNT(*) FROM academic.lecturer_profiles WHERE profile_status = 'active'
                ) AS total_lecturers,
                (
                    SELECT COUNT(*) FROM (
                        SELECT
                            roster.student_id,
                            100.0 * COUNT(*) FILTER (WHERE record.attendance_status IN ('present', 'late'))
                                / NULLIF(COUNT(*), 0) AS rate
                        FROM attendance_session.sessions AS session
                        JOIN attendance_session.session_students AS roster
                            ON roster.session_id = session.id
                        LEFT JOIN attendance_verification.attendance_records AS record
                            ON record.session_id = session.id AND record.student_id = roster.student_id
                        WHERE session.closed_at IS NOT NULL AND session.cancelled_at IS NULL
                        GROUP BY roster.student_id
                    ) AS student_rates
                    WHERE rate < $1
                ) AS students_at_risk_count
            """,
            AT_RISK_THRESHOLD_PERCENT,
        )
        return InstitutionSummaryRecord(
            overall_attendance_percent=row["overall_attendance_percent"],
            total_sessions_completed=row["total_sessions_completed"],
            total_students=row["total_students"],
            total_lecturers=row["total_lecturers"],
            students_at_risk_count=row["students_at_risk_count"],
        )

    async def list_attendance_trend(
        self,
        connection: asyncpg.Connection,
        *,
        weeks: int = DEFAULT_TREND_WEEKS,
    ) -> list[WeeklyTrendRecord]:
        rows = await connection.fetch(
            """
            WITH weekly AS (
                SELECT
                    DATE_TRUNC('week', session.scheduled_start_at) AS week_start,
                    COUNT(*) FILTER (WHERE record.attendance_status IN ('present', 'late')) AS present_count,
                    COUNT(*) AS total_count
                FROM attendance_session.sessions AS session
                JOIN attendance_session.session_students AS roster
                    ON roster.session_id = session.id
                LEFT JOIN attendance_verification.attendance_records AS record
                    ON record.session_id = session.id AND record.student_id = roster.student_id
                WHERE session.closed_at IS NOT NULL AND session.cancelled_at IS NULL
                GROUP BY week_start
                ORDER BY week_start DESC
                LIMIT $1
            )
            SELECT
                week_start,
                ROUND(100.0 * present_count / NULLIF(total_count, 0), 1) AS attendance_rate_percent
            FROM weekly
            ORDER BY week_start ASC
            """,
            weeks,
        )
        return [
            WeeklyTrendRecord(
                week_start=row["week_start"],
                attendance_rate_percent=row["attendance_rate_percent"] or Decimal(0),
            )
            for row in rows
        ]

    async def list_attendance_by_faculty(
        self,
        connection: asyncpg.Connection,
    ) -> list[FacultyAttendanceRecord]:
        rows = await connection.fetch(
            """
            SELECT
                faculty.faculty_name,
                ROUND(
                    100.0 * COUNT(*) FILTER (WHERE record.attendance_status IN ('present', 'late'))
                    / NULLIF(COUNT(*), 0),
                    1
                ) AS attendance_rate_percent
            FROM attendance_session.sessions AS session
            JOIN attendance_session.session_students AS roster
                ON roster.session_id = session.id
            LEFT JOIN attendance_verification.attendance_records AS record
                ON record.session_id = session.id AND record.student_id = roster.student_id
            JOIN academic.course_offerings AS offering
                ON offering.id = session.course_offering_id
            JOIN academic.courses AS course
                ON course.id = offering.course_id
            JOIN academic.departments AS department
                ON department.id = course.department_id
            JOIN academic.faculties AS faculty
                ON faculty.id = department.faculty_id
            WHERE session.closed_at IS NOT NULL AND session.cancelled_at IS NULL
            GROUP BY faculty.faculty_name
            ORDER BY faculty.faculty_name ASC
            """,
        )
        return [
            FacultyAttendanceRecord(
                faculty_name=row["faculty_name"],
                attendance_rate_percent=row["attendance_rate_percent"],
            )
            for row in rows
        ]

    async def list_at_risk_courses(
        self,
        connection: asyncpg.Connection,
        *,
        threshold_percent: int = AT_RISK_THRESHOLD_PERCENT,
    ) -> list[AtRiskCourseRecord]:
        rows = await connection.fetch(
            """
            SELECT
                course.course_code,
                course.course_name,
                ROUND(
                    100.0 * COUNT(*) FILTER (WHERE record.attendance_status IN ('present', 'late'))
                    / NULLIF(COUNT(*), 0),
                    1
                ) AS attendance_rate_percent
            FROM attendance_session.sessions AS session
            JOIN attendance_session.session_students AS roster
                ON roster.session_id = session.id
            LEFT JOIN attendance_verification.attendance_records AS record
                ON record.session_id = session.id AND record.student_id = roster.student_id
            JOIN academic.course_offerings AS offering
                ON offering.id = session.course_offering_id
            JOIN academic.courses AS course
                ON course.id = offering.course_id
            WHERE session.closed_at IS NOT NULL AND session.cancelled_at IS NULL
            GROUP BY course.id, course.course_code, course.course_name
            HAVING
                COUNT(*) > 0
                AND (100.0 * COUNT(*) FILTER (WHERE record.attendance_status IN ('present', 'late')) / COUNT(*))
                    < $1
            ORDER BY attendance_rate_percent ASC
            """,
            threshold_percent,
        )
        return [
            AtRiskCourseRecord(
                course_code=row["course_code"],
                course_name=row["course_name"],
                attendance_rate_percent=row["attendance_rate_percent"],
            )
            for row in rows
        ]
