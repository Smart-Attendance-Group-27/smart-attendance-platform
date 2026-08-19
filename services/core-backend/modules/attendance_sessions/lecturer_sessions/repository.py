from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

import asyncpg

SESSION_SCHEDULED_STATUS = "scheduled"

# Session status is derived from timestamps (activated_at/closed_at/cancelled_at),
# not a DB enum — attendance_session.sessions.status has no CHECK constraint and
# existing code only ever compares it to the literal 'active'. See
# database/migrations/README.md and the Stage-1 repo audit for why a new status
# enum was deliberately not invented here.
SESSION_ACTIVE_STATUS = "active"


@dataclass(frozen=True)
class LecturerSessionRecord:
    id: UUID
    course_offering_id: UUID
    course_code: str | None
    course_name: str | None
    classroom_code: str | None
    scheduled_start_at: datetime
    scheduled_end_at: datetime
    check_in_opens_at: datetime | None
    check_in_closes_at: datetime | None
    late_after_at: datetime | None
    activated_at: datetime | None
    closed_at: datetime | None
    cancelled_at: datetime | None
    requires_face_verification: bool
    requires_geofence: bool
    requires_qr: bool
    enrolled_count: int
    present_count: int
    late_count: int
    pending_review_count: int


@dataclass(frozen=True)
class TimetableEntryForSessionRecord:
    id: UUID
    course_offering_id: UUID
    classroom_id: UUID | None
    classroom_latitude: Decimal | None
    classroom_longitude: Decimal | None
    classroom_default_geofence_radius_m: Decimal | None


@dataclass(frozen=True)
class SessionStudentRecord:
    verification_attempt_id: UUID | None
    student_id: UUID
    registration_number: str | None
    full_name: str
    verification_status: str | None
    geofence_status: str | None
    face_status: str | None
    face_similarity_score: Decimal | None
    face_liveness_passed: bool | None
    qr_status: str | None
    attendance_status: str | None
    review_status: str | None
    checked_in_at: datetime | None


_SESSION_COLUMNS = """
    session.id,
    session.course_offering_id,
    course.course_code,
    course.course_name,
    COALESCE(exception_classroom.classroom_code, timetable_classroom.classroom_code) AS classroom_code,
    session.scheduled_start_at,
    session.scheduled_end_at,
    session.check_in_opens_at,
    session.check_in_closes_at,
    session.late_after_at,
    session.activated_at,
    session.closed_at,
    session.cancelled_at,
    session.requires_face_verification,
    session.requires_geofence,
    session.requires_qr,
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
        -- A failed attempt needs review until a manual_reviews row exists for it
        -- with a non-pending status — no row yet also counts as pending, since
        -- nothing auto-creates manual_reviews rows on failure.
        SELECT COUNT(*) FROM attendance_verification.verification_attempts va
        LEFT JOIN attendance_verification.manual_reviews mr ON mr.verification_attempt_id = va.id
        WHERE va.session_id = session.id
          AND va.status = 'failed'
          AND (mr.review_status IS NULL OR mr.review_status = 'pending')
    ) AS pending_review_count
"""

_SESSION_JOINS = """
    FROM attendance_session.sessions AS session
    JOIN academic.course_offerings AS offering
        ON offering.id = session.course_offering_id
    JOIN academic.courses AS course
        ON course.id = offering.course_id
    JOIN academic.course_lecturers AS assignment
        ON assignment.course_offering_id = offering.id
    LEFT JOIN academic.timetable_entries AS timetable
        ON timetable.id = session.timetable_entry_id
    LEFT JOIN academic.classrooms AS timetable_classroom
        ON timetable_classroom.id = timetable.classroom_id
    LEFT JOIN academic.timetable_exceptions AS exception
        ON exception.id = session.timetable_exception_id
    LEFT JOIN academic.classrooms AS exception_classroom
        ON exception_classroom.id = exception.new_classroom_id
"""


def _row_to_record(row: asyncpg.Record) -> LecturerSessionRecord:
    return LecturerSessionRecord(
        id=row["id"],
        course_offering_id=row["course_offering_id"],
        course_code=row["course_code"],
        course_name=row["course_name"],
        classroom_code=row["classroom_code"],
        scheduled_start_at=row["scheduled_start_at"],
        scheduled_end_at=row["scheduled_end_at"],
        check_in_opens_at=row["check_in_opens_at"],
        check_in_closes_at=row["check_in_closes_at"],
        late_after_at=row["late_after_at"],
        activated_at=row["activated_at"],
        closed_at=row["closed_at"],
        cancelled_at=row["cancelled_at"],
        requires_face_verification=bool(row["requires_face_verification"]),
        requires_geofence=bool(row["requires_geofence"]),
        requires_qr=bool(row["requires_qr"]),
        enrolled_count=row["enrolled_count"],
        present_count=row["present_count"],
        late_count=row["late_count"],
        pending_review_count=row["pending_review_count"],
    )


class LecturerSessionRepository:
    async def list_for_lecturer(
        self,
        connection: asyncpg.Connection,
        lecturer_id: UUID,
    ) -> list[LecturerSessionRecord]:
        rows = await connection.fetch(
            f"""
            SELECT {_SESSION_COLUMNS}
            {_SESSION_JOINS}
            WHERE assignment.lecturer_id = $1
            ORDER BY session.scheduled_start_at DESC
            """,
            lecturer_id,
        )
        return [_row_to_record(row) for row in rows]

    async def find_for_lecturer(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
        lecturer_id: UUID,
        *,
        lock_for_update: bool = False,
    ) -> LecturerSessionRecord | None:
        lock_clause = "FOR UPDATE OF session" if lock_for_update else ""
        row = await connection.fetchrow(
            f"""
            SELECT {_SESSION_COLUMNS}
            {_SESSION_JOINS}
            WHERE session.id = $1 AND assignment.lecturer_id = $2
            {lock_clause}
            """,
            session_id,
            lecturer_id,
        )
        if row is None:
            return None
        return _row_to_record(row)

    async def activate(self, connection: asyncpg.Connection, session_id: UUID) -> None:
        await connection.execute(
            """
            UPDATE attendance_session.sessions
            SET activated_at = now(), status = $2, updated_at = now()
            WHERE id = $1
            """,
            session_id,
            SESSION_ACTIVE_STATUS,
        )

    async def close(self, connection: asyncpg.Connection, session_id: UUID) -> None:
        await connection.execute(
            """
            UPDATE attendance_session.sessions
            SET closed_at = now(), updated_at = now()
            WHERE id = $1
            """,
            session_id,
        )

    async def find_timetable_entry_for_lecturer(
        self,
        connection: asyncpg.Connection,
        timetable_entry_id: UUID,
        lecturer_id: UUID,
    ) -> TimetableEntryForSessionRecord | None:
        row = await connection.fetchrow(
            """
            SELECT
                entry.id,
                entry.course_offering_id,
                classroom.id AS classroom_id,
                classroom.latitude AS classroom_latitude,
                classroom.longitude AS classroom_longitude,
                classroom.default_geofence_radius_m AS classroom_default_geofence_radius_m
            FROM academic.timetable_entries AS entry
            JOIN academic.course_offerings AS offering
                ON offering.id = entry.course_offering_id
            JOIN academic.course_lecturers AS assignment
                ON assignment.course_offering_id = offering.id
            LEFT JOIN academic.classrooms AS classroom
                ON classroom.id = entry.classroom_id
            WHERE entry.id = $1
              AND assignment.lecturer_id = $2
              AND entry.status = 'active'
            """,
            timetable_entry_id,
            lecturer_id,
        )
        if row is None:
            return None

        return TimetableEntryForSessionRecord(
            id=row["id"],
            course_offering_id=row["course_offering_id"],
            classroom_id=row["classroom_id"],
            classroom_latitude=row["classroom_latitude"],
            classroom_longitude=row["classroom_longitude"],
            classroom_default_geofence_radius_m=row["classroom_default_geofence_radius_m"],
        )

    async def create_session(
        self,
        connection: asyncpg.Connection,
        *,
        session_id: UUID,
        course_offering_id: UUID,
        timetable_entry_id: UUID,
        created_by: UUID,
        session_title: str,
        session_type: str,
        scheduled_start_at: datetime,
        scheduled_end_at: datetime,
        check_in_opens_at: datetime,
        check_in_closes_at: datetime,
        late_after_at: datetime,
        requires_face_verification: bool,
        requires_geofence: bool,
        requires_qr: bool,
    ) -> None:
        await connection.execute(
            """
            INSERT INTO attendance_session.sessions (
                id, course_offering_id, timetable_entry_id, timetable_exception_id,
                created_by, session_title, session_type,
                scheduled_start_at, scheduled_end_at,
                check_in_opens_at, check_in_closes_at, late_after_at,
                status, requires_face_verification, requires_geofence, requires_qr,
                activated_at, closed_at, cancelled_at, cancellation_reason,
                created_at, updated_at
            )
            VALUES (
                $1, $2, $3, NULL,
                $4, $5, $6,
                $7, $8,
                $9, $10, $11,
                $12, $13, $14, $15,
                NULL, NULL, NULL, NULL,
                now(), now()
            )
            """,
            session_id,
            course_offering_id,
            timetable_entry_id,
            created_by,
            session_title,
            session_type,
            scheduled_start_at,
            scheduled_end_at,
            check_in_opens_at,
            check_in_closes_at,
            late_after_at,
            SESSION_SCHEDULED_STATUS,
            requires_face_verification,
            requires_geofence,
            requires_qr,
        )

    async def create_session_students_from_enrolments(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
        course_offering_id: UUID,
    ) -> int:
        rows = await connection.fetch(
            """
            INSERT INTO attendance_session.session_students (
                id, session_id, student_id, course_enrolment_id, created_at
            )
            SELECT gen_random_uuid(), $1, enrolment.student_id, enrolment.id, now()
            FROM academic.course_enrolments AS enrolment
            WHERE enrolment.course_offering_id = $2
              AND enrolment.enrolment_status = 'enrolled'
            ON CONFLICT (session_id, student_id) DO NOTHING
            RETURNING id
            """,
            session_id,
            course_offering_id,
        )
        return len(rows)

    async def create_session_geofence(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
        *,
        centre_latitude: Decimal,
        centre_longitude: Decimal,
        radius_m: Decimal,
        accuracy_buffer_m: Decimal,
        maximum_allowed_accuracy_m: Decimal,
    ) -> None:
        await connection.execute(
            """
            INSERT INTO attendance_session.session_geofences (
                session_id, centre_latitude, centre_longitude, radius_m,
                accuracy_buffer_m, maximum_allowed_accuracy_m,
                created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, now(), now())
            """,
            session_id,
            centre_latitude,
            centre_longitude,
            radius_m,
            accuracy_buffer_m,
            maximum_allowed_accuracy_m,
        )

    async def list_students_for_session(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
    ) -> list[SessionStudentRecord]:
        rows = await connection.fetch(
            """
            SELECT
                va.id AS verification_attempt_id,
                student.id AS student_id,
                student.registration_number,
                TRIM(
                    CONCAT_WS(
                        ' ',
                        student.first_name,
                        NULLIF(student.middle_name, ''),
                        student.last_name
                    )
                ) AS full_name,
                va.status AS verification_status,
                va.started_at AS checked_in_at,
                geofence.validation_status AS geofence_status,
                face.validation_status AS face_status,
                face.similarity_score AS face_similarity_score,
                face.liveness_passed AS face_liveness_passed,
                qr.validation_status AS qr_status,
                record.attendance_status,
                CASE
                    WHEN review.review_status IS NOT NULL THEN review.review_status
                    WHEN va.status = 'failed' THEN 'pending'
                    ELSE NULL
                END AS review_status
            FROM attendance_session.session_students AS ss
            JOIN academic.student_profiles AS student
                ON student.id = ss.student_id
            LEFT JOIN attendance_verification.verification_attempts AS va
                ON va.session_id = ss.session_id AND va.student_id = ss.student_id
            LEFT JOIN LATERAL (
                SELECT g.validation_status
                FROM attendance_verification.geofence_validation_attempts AS g
                WHERE g.verification_attempt_id = va.id
                ORDER BY g.attempt_number DESC
                LIMIT 1
            ) AS geofence ON va.id IS NOT NULL
            LEFT JOIN LATERAL (
                SELECT f.validation_status, f.similarity_score, f.liveness_passed
                FROM face_verification.face_validation_attempts AS f
                WHERE f.verification_attempt_id = va.id
                ORDER BY f.attempt_number DESC
                LIMIT 1
            ) AS face ON va.id IS NOT NULL
            LEFT JOIN LATERAL (
                SELECT q.validation_status
                FROM attendance_verification.qr_validation_attempts AS q
                WHERE q.verification_attempt_id = va.id
                ORDER BY q.attempt_number DESC
                LIMIT 1
            ) AS qr ON va.id IS NOT NULL
            LEFT JOIN attendance_verification.attendance_records AS record
                ON record.session_id = ss.session_id AND record.student_id = ss.student_id
            LEFT JOIN attendance_verification.manual_reviews AS review
                ON review.verification_attempt_id = va.id
            WHERE ss.session_id = $1
            ORDER BY full_name ASC
            """,
            session_id,
        )

        return [
            SessionStudentRecord(
                verification_attempt_id=row["verification_attempt_id"],
                student_id=row["student_id"],
                registration_number=row["registration_number"],
                full_name=row["full_name"] or "",
                verification_status=row["verification_status"],
                geofence_status=row["geofence_status"],
                face_status=row["face_status"],
                face_similarity_score=row["face_similarity_score"],
                face_liveness_passed=row["face_liveness_passed"],
                qr_status=row["qr_status"],
                attendance_status=row["attendance_status"],
                review_status=row["review_status"],
                checked_in_at=row["checked_in_at"],
            )
            for row in rows
        ]
