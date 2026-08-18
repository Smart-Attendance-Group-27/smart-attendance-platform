from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import asyncpg

from modules.academic.student_courses.repository import (
    StudentAttendanceRecord,
    StudentCourseRecord,
    StudentCourseRepository,
    StudentCourseSessionRecord,
)
from modules.academic.student_profile.exception import StudentProfileNotFoundError
from modules.academic.student_profile.repository import StudentProfileRepository

ACTIVE_PROFILE_STATUS = "active"


@dataclass(frozen=True)
class StudentCourseSession:
    id: UUID
    title: str
    time_text: str
    type: str
    status: str
    recorded_time: str | None
    week_header: str


@dataclass(frozen=True)
class StudentCourseAttendanceRecord:
    id: UUID
    day: str
    month: str
    title: str
    recorded_text: str
    status: str


@dataclass(frozen=True)
class StudentCourse:
    id: UUID
    code: str
    title: str
    lecturer: str
    semester: str
    attended_sessions: int
    total_sessions: int
    attendance_percentage: int
    sessions: list[StudentCourseSession]
    attendance_records: list[StudentCourseAttendanceRecord]


class StudentCourseService:
    def __init__(
        self,
        repository: StudentCourseRepository | None = None,
        student_profile_repository: StudentProfileRepository | None = None,
    ) -> None:
        self._repository = repository or StudentCourseRepository()
        self._student_profile_repository = (
            student_profile_repository or StudentProfileRepository()
        )

    async def list_courses_for_user(
        self,
        pool: asyncpg.Pool,
        user_id: UUID,
    ) -> list[StudentCourse]:
        async with pool.acquire() as connection:
            profile = await self._student_profile_repository.find_by_user_id(
                connection,
                user_id,
            )
            if profile is None or profile.profile_status != ACTIVE_PROFILE_STATUS:
                raise StudentProfileNotFoundError(
                    "No active student profile exists for this account."
                )

            course_rows = await self._repository.list_courses_for_student(
                connection,
                profile.id,
            )
            session_rows = await self._repository.list_sessions_for_student_courses(
                connection,
                profile.id,
            )
            attendance_rows = (
                await self._repository.list_attendance_records_for_student_courses(
                    connection,
                    profile.id,
                )
            )

        sessions_by_course = _group_sessions_by_course(session_rows)
        records_by_course = _group_attendance_records_by_course(attendance_rows)

        return [
            StudentCourse(
                id=course.course_offering_id,
                code=course.course_code or "",
                title=course.course_name or "",
                lecturer=course.lecturers or "Lecturer not assigned",
                semester=_format_semester(course),
                attended_sessions=course.attended_sessions,
                total_sessions=course.total_sessions,
                attendance_percentage=_format_attendance_percentage(
                    course.attendance_percentage,
                ),
                sessions=sessions_by_course.get(course.course_offering_id, []),
                attendance_records=records_by_course.get(course.course_offering_id, []),
            )
            for course in course_rows
        ]


def _group_sessions_by_course(
    session_rows: list[StudentCourseSessionRecord],
) -> dict[UUID, list[StudentCourseSession]]:
    grouped: dict[UUID, list[StudentCourseSession]] = {}
    now = datetime.now(timezone.utc)

    for row in session_rows:
        grouped.setdefault(row.course_offering_id, []).append(
            StudentCourseSession(
                id=row.id,
                title=row.session_title or "Attendance session",
                time_text=_format_session_time(row),
                type=_format_session_type(row.session_type),
                status=_derive_session_status(row, now),
                recorded_time=_format_recorded_time(row.attendance_recorded_at),
                week_header=_format_week_header(row.scheduled_start_at, now),
            )
        )

    return grouped


def _group_attendance_records_by_course(
    attendance_rows: list[StudentAttendanceRecord],
) -> dict[UUID, list[StudentCourseAttendanceRecord]]:
    grouped: dict[UUID, list[StudentCourseAttendanceRecord]] = {}

    for row in attendance_rows:
        if row.created_at is None:
            continue

        grouped.setdefault(row.course_offering_id, []).append(
            StudentCourseAttendanceRecord(
                id=row.id,
                day=row.created_at.strftime("%d"),
                month=row.created_at.strftime("%b").upper(),
                title=row.session_title or "Attendance session",
                recorded_text=_format_recorded_time(row.created_at)
                or "Recorded",
                status=_format_attendance_status(row.attendance_status),
            )
        )

    return grouped


def _format_semester(course: StudentCourseRecord) -> str:
    parts: list[str] = []
    if course.semester_number is not None:
        parts.append(f"Semester {course.semester_number}")

    start = course.academic_year_start
    if isinstance(start, datetime):
        parts.append(str(start.year))
    elif isinstance(start, date):
        parts.append(str(start.year))

    return ", ".join(parts) or "Current semester"


def _format_attendance_percentage(value: Decimal | None) -> int:
    if value is None:
        return 0
    return int(round(float(value)))


def _format_session_time(row: StudentCourseSessionRecord) -> str:
    start = _as_utc(row.scheduled_start_at)
    end = _as_utc(row.scheduled_end_at)
    day_label = _format_day_label(start)
    time_range = f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}"
    venue = row.venue or "Venue TBA"
    session_type = _format_session_type(row.session_type)
    return f"{day_label} · {time_range} · {venue} · {session_type}"


def _format_day_label(value: datetime) -> str:
    today = datetime.now(timezone.utc).date()
    session_date = value.date()
    if session_date == today:
        return "Today"
    if session_date == today + timedelta(days=1):
        return "Tomorrow"
    return value.strftime("%d %b")


def _format_session_type(value: str | None) -> str:
    normalized = (value or "lecture").replace("_", " ").strip()
    return normalized[:1].upper() + normalized[1:]


def _derive_session_status(
    row: StudentCourseSessionRecord,
    now: datetime,
) -> str:
    if row.attendance_status in {"present", "late"}:
        return "marked"
    if row.cancelled_at is not None or row.closed_at is not None:
        return "closed"

    check_in_opens_at = _as_utc(row.check_in_opens_at or row.scheduled_start_at)
    check_in_closes_at = _as_utc(row.check_in_closes_at or row.scheduled_end_at)

    if row.status == "active" and check_in_opens_at <= now < check_in_closes_at:
        return "active"
    if check_in_opens_at > now:
        return "upcoming"
    if check_in_closes_at <= now and row.attendance_status is None:
        return "missed"
    return "closed"


def _format_recorded_time(value: datetime | None) -> str | None:
    if value is None:
        return None
    return f"Recorded at {_as_utc(value).strftime('%H:%M')}"


def _format_attendance_status(value: str | None) -> str:
    if value in {"present", "late"}:
        return "Present"
    return "Absent"


def _format_week_header(value: datetime, now: datetime) -> str:
    value_date = _as_utc(value).date()
    today = now.date()

    if value_date >= today:
        return "This week"

    start = value_date
    end = value_date
    return f"{start.strftime('%d %b')}-{end.strftime('%d %b')}"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
