from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg


@dataclass(frozen=True)
class ActiveAttendanceSessionRecord:
    id: UUID
    course_code: str | None
    course_name: str | None
    session_title: str | None
    session_type: str | None
    lecturer_names: str | None
    scheduled_start_at: datetime
    scheduled_end_at: datetime
    check_in_opens_at: datetime
    check_in_closes_at: datetime
    late_after_at: datetime | None
    venue: str | None
    requires_face_verification: bool
    requires_geofence: bool
    requires_qr: bool


class ActiveAttendanceSessionRepository:
    async def list_open_geofence_sessions_for_student(
        self,
        connection: asyncpg.Connection,
        student_id: UUID,
        current_time: datetime,
    ) -> list[ActiveAttendanceSessionRecord]:
        rows = await connection.fetch(
            """
            SELECT
                session.id,
                course.course_code,
                course.course_name,
                session.session_title,
                session.session_type,
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
                ) AS lecturer_names,
                session.scheduled_start_at,
                session.scheduled_end_at,
                session.check_in_opens_at,
                session.check_in_closes_at,
                session.late_after_at,
                COALESCE(
                    exception_classroom.classroom_code,
                    timetable_classroom.classroom_code
                ) AS venue,
                session.requires_face_verification,
                session.requires_geofence,
                session.requires_qr
            FROM attendance_session.session_students AS eligible_student
            JOIN attendance_session.sessions AS session
                ON session.id = eligible_student.session_id
            JOIN academic.course_offerings AS offering
                ON offering.id = session.course_offering_id
            JOIN academic.courses AS course
                ON course.id = offering.course_id
            LEFT JOIN academic.course_lecturers AS assignment
                ON assignment.course_offering_id = offering.id
            LEFT JOIN academic.lecturer_profiles AS lecturer
                ON lecturer.id = assignment.lecturer_id
            LEFT JOIN academic.timetable_entries AS timetable
                ON timetable.id = session.timetable_entry_id
            LEFT JOIN academic.classrooms AS timetable_classroom
                ON timetable_classroom.id = timetable.classroom_id
            LEFT JOIN academic.timetable_exceptions AS timetable_exception
                ON timetable_exception.id = session.timetable_exception_id
            LEFT JOIN academic.classrooms AS exception_classroom
                ON exception_classroom.id = timetable_exception.new_classroom_id
            WHERE eligible_student.student_id = $1
              AND session.status = 'active'
              AND session.closed_at IS NULL
              AND session.cancelled_at IS NULL
              AND session.requires_geofence IS TRUE
              AND session.scheduled_start_at IS NOT NULL
              AND session.scheduled_end_at IS NOT NULL
              AND session.check_in_opens_at IS NOT NULL
              AND session.check_in_closes_at IS NOT NULL
              AND session.check_in_opens_at <= $2
              AND session.check_in_closes_at > $2
            GROUP BY
                session.id,
                course.course_code,
                course.course_name,
                session.session_title,
                session.session_type,
                session.scheduled_start_at,
                session.scheduled_end_at,
                session.check_in_opens_at,
                session.check_in_closes_at,
                session.late_after_at,
                exception_classroom.classroom_code,
                timetable_classroom.classroom_code,
                session.requires_face_verification,
                session.requires_geofence,
                session.requires_qr
            ORDER BY session.scheduled_start_at ASC, session.id ASC
            """,
            student_id,
            current_time,
        )

        return [
            ActiveAttendanceSessionRecord(
                id=row["id"],
                course_code=row["course_code"],
                course_name=row["course_name"],
                session_title=row["session_title"],
                session_type=row["session_type"],
                lecturer_names=row["lecturer_names"],
                scheduled_start_at=row["scheduled_start_at"],
                scheduled_end_at=row["scheduled_end_at"],
                check_in_opens_at=row["check_in_opens_at"],
                check_in_closes_at=row["check_in_closes_at"],
                late_after_at=row["late_after_at"],
                venue=row["venue"],
                requires_face_verification=bool(row["requires_face_verification"]),
                requires_geofence=bool(row["requires_geofence"]),
                requires_qr=bool(row["requires_qr"]),
            )
            for row in rows
        ]
