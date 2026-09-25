import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone, tzinfo
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import asyncpg

from modules.academic.student_courses.repository import (
    StudentCourseRecord,
    StudentCourseRepository,
    StudentCourseSessionRecord,
)
from modules.academic.student_profile.exception import StudentProfileNotFoundError
from modules.academic.student_profile.repository import StudentProfileRepository

logger = logging.getLogger(__name__)

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
    starts_at: datetime
    ends_at: datetime
    venue: str | None


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
    # 0 until a session of the course has been closed (see total_sessions).
    attendance_percentage: int
    # The offering's own attendance requirement; None when none is configured.
    attendance_threshold_percent: float | None
    sessions: list[StudentCourseSession]
    attendance_records: list[StudentCourseAttendanceRecord]


def resolve_time_zone(name: str) -> tzinfo:
    """The institution timezone, or UTC (with a warning) if the name is unknown."""
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("Unknown APP_TIMEZONE %r; falling back to UTC", name)
        return timezone.utc


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
        time_zone_name: str = "UTC",
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
        zone = resolve_time_zone(time_zone_name)
        sessions_by_course = _group_sessions_by_course(session_rows, zone)
        records_by_course = _group_attendance_records_by_course(session_rows, zone)

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
                attendance_threshold_percent=(
                    float(course.attendance_threshold)
                    if course.attendance_threshold is not None
                    else None
                ),
                sessions=sessions_by_course.get(course.course_offering_id, []),
                attendance_records=records_by_course.get(course.course_offering_id, []),
            )
            for course in course_rows
        ]


def _group_sessions_by_course(
    session_rows: list[StudentCourseSessionRecord],
    zone: tzinfo = timezone.utc,
    now: datetime | None = None,
) -> dict[UUID, list[StudentCourseSession]]:
    grouped: dict[UUID, list[StudentCourseSession]] = {}
    now = now or datetime.now(timezone.utc)

    for row in session_rows:
        grouped.setdefault(row.course_offering_id, []).append(
            StudentCourseSession(
                id=row.id,
                title=row.session_title or "Attendance session",
                time_text=_format_session_time(row, zone, now),
                type=_format_session_type(row.session_type),
                status=_derive_session_status(row, now),
                recorded_time=_format_recorded_time(row.attendance_recorded_at, zone),
                week_header=_format_week_header(row.scheduled_start_at, zone, now),
                starts_at=_as_utc(row.scheduled_start_at),
                ends_at=_as_utc(row.scheduled_end_at),
                venue=row.venue,
            )
        )

    return grouped


def _group_attendance_records_by_course(
    session_rows: list[StudentCourseSessionRecord],
    zone: tzinfo = timezone.utc,
    now: datetime | None = None,
) -> dict[UUID, list[StudentCourseAttendanceRecord]]:
    grouped: dict[UUID, list[StudentCourseAttendanceRecord]] = {}
    now = now or datetime.now(timezone.utc)

    for row in session_rows:
        status = _derive_session_status(row, now)
        if status == "cancelled":
            recorded_text = "Session cancelled"
        else:
            recorded_text = _format_recorded_time(row.attendance_recorded_at, zone) or {
                "absent": "No attendance recorded",
                "active": "Check-in open",
                "upcoming": "Session upcoming",
            }.get(status, "Awaiting final attendance")
        local_start = _as_utc(row.scheduled_start_at).astimezone(zone)
        grouped.setdefault(row.course_offering_id, []).append(
            StudentCourseAttendanceRecord(
                id=row.id,
                day=local_start.strftime("%d"),
                month=local_start.strftime("%b").upper(),
                title=row.session_title or "Attendance session",
                recorded_text=recorded_text,
                status={
                    "marked": "Present",
                    "late": "Late",
                    "absent": "Absent",
                    "cancelled": "Cancelled",
                }.get(status, "Awaiting"),
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


def _format_session_time(
    row: StudentCourseSessionRecord,
    zone: tzinfo,
    now: datetime,
) -> str:
    start = _as_utc(row.scheduled_start_at).astimezone(zone)
    end = _as_utc(row.scheduled_end_at).astimezone(zone)
    day_label = _format_day_label(start, now.astimezone(zone).date())
    time_range = f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}"
    venue = row.venue or "Venue TBA"
    session_type = _format_session_type(row.session_type)
    return f"{day_label} · {time_range} · {venue} · {session_type}"


def _format_day_label(local_start: datetime, today: date) -> str:
    session_date = local_start.date()
    if session_date == today:
        return "Today"
    if session_date == today + timedelta(days=1):
        return "Tomorrow"
    return local_start.strftime("%d %b")


def _format_session_type(value: str | None) -> str:
    normalized = (value or "lecture").replace("_", " ").strip()
    return normalized[:1].upper() + normalized[1:]


def _derive_session_status(
    row: StudentCourseSessionRecord,
    now: datetime,
) -> str:
    if row.cancelled_at is not None:
        return "cancelled"
    if row.attendance_status == "present":
        return "marked"
    if row.attendance_status == "late":
        return "late"
    if row.attendance_status == "absent" or row.closed_at is not None:
        return "absent"

    check_in_opens_at = _as_utc(row.check_in_opens_at or row.scheduled_start_at)
    check_in_closes_at = _as_utc(row.check_in_closes_at or row.scheduled_end_at)

    if row.status == "active" and check_in_opens_at <= now < check_in_closes_at:
        return "active"
    if check_in_opens_at > now:
        return "upcoming"
    return "awaiting"


def _format_recorded_time(value: datetime | None, zone: tzinfo) -> str | None:
    if value is None:
        return None
    return f"Recorded at {_as_utc(value).astimezone(zone).strftime('%H:%M')}"


def _format_week_header(value: datetime, zone: tzinfo, now: datetime) -> str:
    """Groups sessions by the Monday-Sunday week they fall in, in local time."""
    session_date = _as_utc(value).astimezone(zone).date()
    today = now.astimezone(zone).date()

    session_monday = session_date - timedelta(days=session_date.weekday())
    this_monday = today - timedelta(days=today.weekday())
    weeks_apart = (session_monday - this_monday).days // 7

    if weeks_apart == 0:
        return "This week"
    if weeks_apart == 1:
        return "Next week"
    if weeks_apart == -1:
        return "Last week"

    session_sunday = session_monday + timedelta(days=6)
    return f"{session_monday.strftime('%d %b')}–{session_sunday.strftime('%d %b')}"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
