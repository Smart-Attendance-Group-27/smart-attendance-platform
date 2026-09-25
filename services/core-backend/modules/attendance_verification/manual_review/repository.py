from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

import asyncpg

from modules.attendance_verification.attendance_state import AttendanceRecordSource

FAILED_ATTEMPT_STATUS = "failed"


@dataclass(frozen=True)
class ManualReviewQueueItemRecord:
    verification_attempt_id: UUID
    session_id: UUID
    course_code: str | None
    course_name: str | None
    classroom_code: str | None
    scheduled_start_at: datetime
    student_id: UUID
    registration_number: str | None
    full_name: str
    failure_reason: str | None
    started_at: datetime | None
    completed_at: datetime | None
    geofence_status: str | None
    geofence_failure_reason: str | None
    face_status: str | None
    face_similarity_score: Decimal | None
    face_liveness_passed: bool | None
    qr_status: str | None
    review_status: str | None
    decision_reason: str | None
    reviewed_at: datetime | None
    # The similarity threshold that was configured for the face comparison.
    face_similarity_threshold: Decimal | None = None


@dataclass(frozen=True)
class VerificationAttemptDetailRecord:
    id: UUID
    session_id: UUID
    student_id: UUID
    status: str | None


@dataclass(frozen=True)
class AttendanceRecordRecord:
    id: UUID
    attendance_status: str | None
    record_source: str | None
    manual_reason: str | None


@dataclass(frozen=True)
class ManualReviewRecord:
    verification_attempt_id: UUID
    review_status: str | None
    reviewed_by: UUID | None
    decision_reason: str | None
    reviewed_at: datetime | None


_QUEUE_COLUMNS = """
    va.id AS verification_attempt_id,
    session.id AS session_id,
    course.course_code,
    course.course_name,
    COALESCE(exception_classroom.classroom_code, timetable_classroom.classroom_code) AS classroom_code,
    session.scheduled_start_at,
    student.id AS student_id,
    student.registration_number,
    TRIM(
        CONCAT_WS(' ', student.first_name, NULLIF(student.middle_name, ''), student.last_name)
    ) AS full_name,
    va.failure_reason,
    va.started_at,
    va.completed_at,
    geofence.validation_status AS geofence_status,
    geofence.failure_reason AS geofence_failure_reason,
    face.validation_status AS face_status,
    face.similarity_score AS face_similarity_score,
    face.liveness_passed AS face_liveness_passed,
    face.similarity_threshold AS face_similarity_threshold,
    qr.validation_status AS qr_status,
    review.review_status,
    review.decision_reason,
    review.reviewed_at
"""

_QUEUE_JOINS = """
    FROM attendance_verification.verification_attempts AS va
    JOIN attendance_session.sessions AS session
        ON session.id = va.session_id
    JOIN academic.course_offerings AS offering
        ON offering.id = session.course_offering_id
    JOIN academic.courses AS course
        ON course.id = offering.course_id
    JOIN academic.course_lecturers AS assignment
        ON assignment.course_offering_id = offering.id
    JOIN academic.student_profiles AS student
        ON student.id = va.student_id
    LEFT JOIN academic.timetable_entries AS timetable
        ON timetable.id = session.timetable_entry_id
    LEFT JOIN academic.classrooms AS timetable_classroom
        ON timetable_classroom.id = timetable.classroom_id
    LEFT JOIN academic.timetable_exceptions AS exception
        ON exception.id = session.timetable_exception_id
    LEFT JOIN academic.classrooms AS exception_classroom
        ON exception_classroom.id = exception.new_classroom_id
    LEFT JOIN LATERAL (
        SELECT g.validation_status, g.failure_reason
        FROM attendance_verification.geofence_validation_attempts AS g
        WHERE g.verification_attempt_id = va.id
        ORDER BY g.attempt_number DESC
        LIMIT 1
    ) AS geofence ON TRUE
    LEFT JOIN LATERAL (
        SELECT f.validation_status, f.similarity_score, f.liveness_passed,
               config.similarity_threshold
        FROM face_verification.face_validation_attempts AS f
        LEFT JOIN face_verification.verification_configs AS config
            ON config.id = f.verification_config_id
        WHERE f.verification_attempt_id = va.id
        ORDER BY f.attempt_number DESC
        LIMIT 1
    ) AS face ON TRUE
    LEFT JOIN LATERAL (
        SELECT q.validation_status
        FROM attendance_verification.qr_validation_attempts AS q
        WHERE q.verification_attempt_id = va.id
        ORDER BY q.attempt_number DESC
        LIMIT 1
    ) AS qr ON TRUE
    LEFT JOIN attendance_verification.manual_reviews AS review
        ON review.verification_attempt_id = va.id
"""


def _row_to_queue_item(row: asyncpg.Record) -> ManualReviewQueueItemRecord:
    return ManualReviewQueueItemRecord(
        verification_attempt_id=row["verification_attempt_id"],
        session_id=row["session_id"],
        course_code=row["course_code"],
        course_name=row["course_name"],
        classroom_code=row["classroom_code"],
        scheduled_start_at=row["scheduled_start_at"],
        student_id=row["student_id"],
        registration_number=row["registration_number"],
        full_name=row["full_name"] or "",
        failure_reason=row["failure_reason"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        geofence_status=row["geofence_status"],
        geofence_failure_reason=row["geofence_failure_reason"],
        face_status=row["face_status"],
        face_similarity_score=row["face_similarity_score"],
        face_liveness_passed=row["face_liveness_passed"],
        face_similarity_threshold=row["face_similarity_threshold"],
        qr_status=row["qr_status"],
        review_status=row["review_status"],
        decision_reason=row["decision_reason"],
        reviewed_at=row["reviewed_at"],
    )


class ManualReviewRepository:
    async def list_queue_for_lecturer(
        self,
        connection: asyncpg.Connection,
        lecturer_id: UUID,
        *,
        session_id: UUID | None = None,
    ) -> list[ManualReviewQueueItemRecord]:
        session_clause = "AND session.id = $2" if session_id is not None else ""
        params = [lecturer_id] if session_id is None else [lecturer_id, session_id]
        rows = await connection.fetch(
            f"""
            SELECT {_QUEUE_COLUMNS}
            {_QUEUE_JOINS}
            WHERE assignment.lecturer_id = $1
              AND va.status = '{FAILED_ATTEMPT_STATUS}'
              AND (review.review_status IS NULL OR review.review_status = 'pending')
              AND NOT EXISTS (
                SELECT 1 FROM attendance_verification.attendance_records AS manual_record
                WHERE manual_record.session_id = va.session_id
                  AND manual_record.student_id = va.student_id
                  AND manual_record.record_source = '{AttendanceRecordSource.MANUAL.value}'
              )
              {session_clause}
            ORDER BY va.completed_at DESC NULLS LAST, va.started_at DESC
            """,
            *params,
        )
        return [_row_to_queue_item(row) for row in rows]

    async def find_queue_item_for_lecturer(
        self,
        connection: asyncpg.Connection,
        verification_attempt_id: UUID,
        lecturer_id: UUID,
    ) -> ManualReviewQueueItemRecord | None:
        row = await connection.fetchrow(
            f"""
            SELECT {_QUEUE_COLUMNS}
            {_QUEUE_JOINS}
            WHERE va.id = $1 AND assignment.lecturer_id = $2
            """,
            verification_attempt_id,
            lecturer_id,
        )
        if row is None:
            return None
        return _row_to_queue_item(row)

    async def find_attempt_for_lecturer(
        self,
        connection: asyncpg.Connection,
        verification_attempt_id: UUID,
        lecturer_id: UUID,
        *,
        lock_for_update: bool = False,
    ) -> VerificationAttemptDetailRecord | None:
        lock_clause = "FOR UPDATE OF va" if lock_for_update else ""
        row = await connection.fetchrow(
            f"""
            SELECT va.id, va.session_id, va.student_id, va.status
            FROM attendance_verification.verification_attempts AS va
            JOIN attendance_session.sessions AS session
                ON session.id = va.session_id
            JOIN academic.course_offerings AS offering
                ON offering.id = session.course_offering_id
            JOIN academic.course_lecturers AS assignment
                ON assignment.course_offering_id = offering.id
            WHERE va.id = $1 AND assignment.lecturer_id = $2
            {lock_clause}
            """,
            verification_attempt_id,
            lecturer_id,
        )
        if row is None:
            return None
        return VerificationAttemptDetailRecord(
            id=row["id"],
            session_id=row["session_id"],
            student_id=row["student_id"],
            status=row["status"],
        )

    async def find_attendance_record(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
        student_id: UUID,
    ) -> AttendanceRecordRecord | None:
        row = await connection.fetchrow(
            """
            SELECT id, attendance_status, record_source, manual_reason
            FROM attendance_verification.attendance_records
            WHERE session_id = $1 AND student_id = $2
            """,
            session_id,
            student_id,
        )
        if row is None:
            return None
        return AttendanceRecordRecord(
            id=row["id"],
            attendance_status=row["attendance_status"],
            record_source=row["record_source"],
            manual_reason=row["manual_reason"],
        )

    async def find_manual_review(
        self,
        connection: asyncpg.Connection,
        verification_attempt_id: UUID,
    ) -> ManualReviewRecord | None:
        row = await connection.fetchrow(
            """
            SELECT verification_attempt_id, review_status, reviewed_by, decision_reason, reviewed_at
            FROM attendance_verification.manual_reviews
            WHERE verification_attempt_id = $1
            """,
            verification_attempt_id,
        )
        if row is None:
            return None
        return ManualReviewRecord(
            verification_attempt_id=row["verification_attempt_id"],
            review_status=row["review_status"],
            reviewed_by=row["reviewed_by"],
            decision_reason=row["decision_reason"],
            reviewed_at=row["reviewed_at"],
        )

    async def upsert_manual_review(
        self,
        connection: asyncpg.Connection,
        *,
        verification_attempt_id: UUID,
        review_status: str,
        reviewed_by: UUID,
        decision_reason: str | None,
    ) -> None:
        await connection.execute(
            """
            INSERT INTO attendance_verification.manual_reviews (
                verification_attempt_id, review_status, reviewed_by, decision_reason, reviewed_at
            )
            VALUES ($1, $2, $3, $4, now())
            ON CONFLICT (verification_attempt_id) DO UPDATE
            SET review_status = EXCLUDED.review_status,
                reviewed_by = EXCLUDED.reviewed_by,
                decision_reason = EXCLUDED.decision_reason,
                reviewed_at = now()
            """,
            verification_attempt_id,
            review_status,
            reviewed_by,
            decision_reason,
        )
