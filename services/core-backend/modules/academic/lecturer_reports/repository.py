from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

import asyncpg


@dataclass(frozen=True)
class LecturerOverviewRecord:
    active_course_count: int
    upcoming_session_count: int
    today_session_count: int
    average_attendance_rate_percent: Decimal | None
    pending_review_count: int


@dataclass(frozen=True)
class CourseSessionReportRecord:
    session_id: UUID
    scheduled_start_at: datetime
    activated_at: datetime | None
    closed_at: datetime | None
    cancelled_at: datetime | None
    enrolled_count: int
    present_count: int
    late_count: int
    absent_count: int
    pending_review_count: int


@dataclass(frozen=True)
class WeeklyTrendRecord:
    week_start: datetime
    attendance_rate_percent: Decimal


@dataclass(frozen=True)
class AtRiskStudentRecord:
    student_id: UUID
    registration_number: str | None
    full_name: str
    course_code: str
    attendance_rate_percent: Decimal
    late_count: int
    last_attended_at: datetime | None


AT_RISK_THRESHOLD_PERCENT = 70


class LecturerReportRepository:
    async def lecturer_owns_course_offering(
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

    async def get_overview_for_lecturer(
        self,
        connection: asyncpg.Connection,
        lecturer_id: UUID,
    ) -> LecturerOverviewRecord:
        row = await connection.fetchrow(
            """
            SELECT
                (
                    SELECT COUNT(*)
                    FROM academic.course_lecturers AS assignment
                    JOIN academic.course_offerings AS offering
                        ON offering.id = assignment.course_offering_id
                    WHERE assignment.lecturer_id = $1 AND offering.status = 'active'
                ) AS active_course_count,
                (
                    SELECT COUNT(*)
                    FROM attendance_session.sessions AS session
                    JOIN academic.course_offerings AS offering
                        ON offering.id = session.course_offering_id
                    JOIN academic.course_lecturers AS assignment
                        ON assignment.course_offering_id = offering.id
                    WHERE assignment.lecturer_id = $1
                      AND session.cancelled_at IS NULL
                      AND session.activated_at IS NULL
                      AND session.scheduled_start_at > now()
                ) AS upcoming_session_count,
                (
                    SELECT COUNT(*)
                    FROM attendance_session.sessions AS session
                    JOIN academic.course_offerings AS offering
                        ON offering.id = session.course_offering_id
                    JOIN academic.course_lecturers AS assignment
                        ON assignment.course_offering_id = offering.id
                    WHERE assignment.lecturer_id = $1
                      AND session.cancelled_at IS NULL
                      AND session.scheduled_start_at::date = now()::date
                ) AS today_session_count,
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
                    JOIN academic.course_offerings AS offering
                        ON offering.id = session.course_offering_id
                    JOIN academic.course_lecturers AS assignment
                        ON assignment.course_offering_id = offering.id
                    WHERE assignment.lecturer_id = $1
                ) AS average_attendance_rate_percent,
                (
                    SELECT COUNT(*)
                    FROM attendance_verification.verification_attempts AS attempt
                    JOIN attendance_session.sessions AS session
                        ON session.id = attempt.session_id
                    JOIN academic.course_offerings AS offering
                        ON offering.id = session.course_offering_id
                    JOIN academic.course_lecturers AS assignment
                        ON assignment.course_offering_id = offering.id
                    LEFT JOIN attendance_verification.manual_reviews AS review
                        ON review.verification_attempt_id = attempt.id
                    WHERE assignment.lecturer_id = $1
                      AND attempt.status = 'failed'
                      AND (review.review_status IS NULL OR review.review_status = 'pending')
                ) AS pending_review_count
            """,
            lecturer_id,
        )
        return LecturerOverviewRecord(
            active_course_count=row["active_course_count"],
            upcoming_session_count=row["upcoming_session_count"],
            today_session_count=row["today_session_count"],
            average_attendance_rate_percent=row["average_attendance_rate_percent"],
            pending_review_count=row["pending_review_count"],
        )

    async def list_session_report_for_course(
        self,
        connection: asyncpg.Connection,
        course_offering_id: UUID,
    ) -> list[CourseSessionReportRecord]:
        rows = await connection.fetch(
            """
            SELECT
                session.id AS session_id,
                session.scheduled_start_at,
                session.activated_at,
                session.closed_at,
                session.cancelled_at,
                (
                    SELECT COUNT(*) FROM attendance_session.session_students ss
                    WHERE ss.session_id = session.id
                ) AS enrolled_count,
                (
                    SELECT COUNT(*) FROM attendance_verification.attendance_records ar
                    WHERE ar.session_id = session.id AND ar.attendance_status = 'present'
                ) AS present_count,
                (
                    SELECT COUNT(*) FROM attendance_verification.attendance_records ar
                    WHERE ar.session_id = session.id AND ar.attendance_status = 'late'
                ) AS late_count,
                (
                    SELECT COUNT(*) FROM attendance_verification.attendance_records ar
                    WHERE ar.session_id = session.id AND ar.attendance_status = 'absent'
                ) AS absent_count,
                (
                    SELECT COUNT(*)
                    FROM attendance_verification.verification_attempts va
                    LEFT JOIN attendance_verification.manual_reviews mr
                        ON mr.verification_attempt_id = va.id
                    WHERE va.session_id = session.id
                      AND va.status = 'failed'
                      AND (mr.review_status IS NULL OR mr.review_status = 'pending')
                ) AS pending_review_count
            FROM attendance_session.sessions AS session
            WHERE session.course_offering_id = $1
            ORDER BY session.scheduled_start_at DESC
            """,
            course_offering_id,
        )
        return [
            CourseSessionReportRecord(
                session_id=row["session_id"],
                scheduled_start_at=row["scheduled_start_at"],
                activated_at=row["activated_at"],
                closed_at=row["closed_at"],
                cancelled_at=row["cancelled_at"],
                enrolled_count=row["enrolled_count"],
                present_count=row["present_count"],
                late_count=row["late_count"],
                absent_count=row["absent_count"],
                pending_review_count=row["pending_review_count"],
            )
            for row in rows
        ]

    async def list_attendance_trend_for_lecturer(
        self,
        connection: asyncpg.Connection,
        lecturer_id: UUID,
        *,
        weeks: int = 8,
    ) -> list[WeeklyTrendRecord]:
        rows = await connection.fetch(
            """
            WITH weekly AS (
                SELECT
                    DATE_TRUNC('week', session.scheduled_start_at) AS week_start,
                    COUNT(*) FILTER (WHERE record.attendance_status IN ('present', 'late')) AS present_count,
                    COUNT(*) AS total_count
                FROM attendance_verification.attendance_records AS record
                JOIN attendance_session.sessions AS session
                    ON session.id = record.session_id
                JOIN academic.course_offerings AS offering
                    ON offering.id = session.course_offering_id
                JOIN academic.course_lecturers AS assignment
                    ON assignment.course_offering_id = offering.id
                WHERE assignment.lecturer_id = $1
                GROUP BY week_start
                ORDER BY week_start DESC
                LIMIT $2
            )
            SELECT
                week_start,
                ROUND(100.0 * present_count / NULLIF(total_count, 0), 1) AS attendance_rate_percent
            FROM weekly
            ORDER BY week_start ASC
            """,
            lecturer_id,
            weeks,
        )
        return [
            WeeklyTrendRecord(
                week_start=row["week_start"],
                attendance_rate_percent=row["attendance_rate_percent"] or Decimal(0),
            )
            for row in rows
        ]

    async def list_at_risk_students_for_lecturer(
        self,
        connection: asyncpg.Connection,
        lecturer_id: UUID,
        *,
        threshold_percent: int = AT_RISK_THRESHOLD_PERCENT,
    ) -> list[AtRiskStudentRecord]:
        rows = await connection.fetch(
            """
            SELECT
                student.id AS student_id,
                student.registration_number,
                TRIM(
                    CONCAT_WS(' ', student.first_name, NULLIF(student.middle_name, ''), student.last_name)
                ) AS full_name,
                course.course_code,
                ROUND(
                    100.0 * COUNT(*) FILTER (WHERE record.attendance_status IN ('present', 'late'))
                    / COUNT(*),
                    1
                ) AS attendance_rate_percent,
                COUNT(*) FILTER (WHERE record.attendance_status = 'late') AS late_count,
                MAX(session.scheduled_start_at) FILTER (
                    WHERE record.attendance_status IN ('present', 'late')
                ) AS last_attended_at
            FROM attendance_verification.attendance_records AS record
            JOIN attendance_session.sessions AS session
                ON session.id = record.session_id
            JOIN academic.course_offerings AS offering
                ON offering.id = session.course_offering_id
            JOIN academic.course_lecturers AS assignment
                ON assignment.course_offering_id = offering.id
            JOIN academic.courses AS course
                ON course.id = offering.course_id
            JOIN academic.student_profiles AS student
                ON student.id = record.student_id
            WHERE assignment.lecturer_id = $1
            GROUP BY student.id, student.registration_number, full_name, course.course_code
            HAVING
                COUNT(*) > 0
                AND (
                    100.0 * COUNT(*) FILTER (WHERE record.attendance_status IN ('present', 'late')) / COUNT(*)
                ) < $2
            ORDER BY attendance_rate_percent ASC
            """,
            lecturer_id,
            threshold_percent,
        )
        return [
            AtRiskStudentRecord(
                student_id=row["student_id"],
                registration_number=row["registration_number"],
                full_name=row["full_name"] or "",
                course_code=row["course_code"],
                attendance_rate_percent=row["attendance_rate_percent"],
                late_count=row["late_count"],
                last_attended_at=row["last_attended_at"],
            )
            for row in rows
        ]
