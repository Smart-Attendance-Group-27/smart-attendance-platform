from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import asyncpg

from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.academic.lecturer_profile.repository import LecturerProfileRepository
from modules.attendance_sessions.lecturer_sessions.exception import (
    ClassroomGeofenceNotConfiguredError,
    InvalidSessionScheduleError,
    SessionAlreadyActiveError,
    SessionAlreadyClosedError,
    SessionCancelledError,
    SessionNotActiveError,
    SessionNotFoundError,
    TimetableEntryNotFoundError,
)
from modules.attendance_sessions.lecturer_sessions.repository import (
    LecturerSessionRecord,
    LecturerSessionRepository,
    SessionStudentRecord,
    TimetableEntryForSessionRecord,
)
from modules.audit.repository import write_audit_log

ACTIVE_PROFILE_STATUS = "active"
ACTOR_TYPE_LECTURER = "lecturer"
AUDIT_ENTITY_TYPE = "attendance_session"

# Same demo/seed defaults used for the one hand-seeded session
# (database/smart_attendance_seed.sql) — no per-session UI for these yet.
DEFAULT_ACCURACY_BUFFER_M = Decimal("10")
DEFAULT_MAXIMUM_ALLOWED_ACCURACY_M = Decimal("50")
DEFAULT_LATE_AFTER_MINUTES = 10


class LecturerSessionService:
    def __init__(
        self,
        repository: LecturerSessionRepository | None = None,
        lecturer_profile_repository: LecturerProfileRepository | None = None,
    ) -> None:
        self._repository = repository or LecturerSessionRepository()
        self._lecturer_profile_repository = (
            lecturer_profile_repository or LecturerProfileRepository()
        )

    async def list_for_user(
        self,
        pool: asyncpg.Pool,
        user_id: UUID,
    ) -> list[LecturerSessionRecord]:
        async with pool.acquire() as connection:
            lecturer_id = await self._resolve_active_lecturer_id(connection, user_id)
            return await self._repository.list_for_lecturer(connection, lecturer_id)

    async def get_for_user(
        self,
        pool: asyncpg.Pool,
        user_id: UUID,
        session_id: UUID,
    ) -> LecturerSessionRecord:
        async with pool.acquire() as connection:
            lecturer_id = await self._resolve_active_lecturer_id(connection, user_id)
            record = await self._repository.find_for_lecturer(connection, session_id, lecturer_id)

        if record is None:
            raise SessionNotFoundError()
        return record

    async def activate_for_user(
        self,
        pool: asyncpg.Pool,
        user_id: UUID,
        session_id: UUID,
    ) -> LecturerSessionRecord:
        async with pool.acquire() as connection, connection.transaction():
            lecturer_id = await self._resolve_active_lecturer_id(connection, user_id)
            record = await self._repository.find_for_lecturer(
                connection,
                session_id,
                lecturer_id,
                lock_for_update=True,
            )
            if record is None:
                raise SessionNotFoundError()
            if record.cancelled_at is not None:
                raise SessionCancelledError()
            if record.closed_at is not None:
                raise SessionAlreadyClosedError()
            if record.activated_at is not None:
                raise SessionAlreadyActiveError()

            await self._repository.activate(connection, session_id)
            updated = await self._repository.find_for_lecturer(connection, session_id, lecturer_id)
            assert updated is not None

            await write_audit_log(
                connection,
                actor_user_id=user_id,
                actor_type=ACTOR_TYPE_LECTURER,
                action="session.activate",
                entity_type=AUDIT_ENTITY_TYPE,
                entity_id=session_id,
                old_values={"activatedAt": None},
                new_values={"activatedAt": updated.activated_at.isoformat()},
            )

        return updated

    async def create_for_user(
        self,
        pool: asyncpg.Pool,
        user_id: UUID,
        *,
        timetable_entry_id: UUID,
        session_title: str,
        session_type: str,
        scheduled_start_at: datetime,
        scheduled_end_at: datetime,
        check_in_opens_at: datetime | None,
        check_in_closes_at: datetime | None,
        late_after_at: datetime | None,
        requires_face_verification: bool,
        requires_geofence: bool,
        requires_qr: bool,
    ) -> LecturerSessionRecord:
        if scheduled_end_at <= scheduled_start_at:
            raise InvalidSessionScheduleError("scheduledEndAt must be after scheduledStartAt.")

        resolved_check_in_opens_at = check_in_opens_at or scheduled_start_at
        resolved_check_in_closes_at = check_in_closes_at or scheduled_end_at
        resolved_late_after_at = late_after_at or (
            scheduled_start_at + timedelta(minutes=DEFAULT_LATE_AFTER_MINUTES)
        )

        if resolved_check_in_closes_at <= resolved_check_in_opens_at:
            raise InvalidSessionScheduleError("checkInClosesAt must be after checkInOpensAt.")
        if not (resolved_check_in_opens_at <= resolved_late_after_at <= resolved_check_in_closes_at):
            raise InvalidSessionScheduleError(
                "lateAfterAt must fall between checkInOpensAt and checkInClosesAt."
            )

        session_id = uuid4()

        async with pool.acquire() as connection, connection.transaction():
            lecturer_id = await self._resolve_active_lecturer_id(connection, user_id)

            entry = await self._repository.find_timetable_entry_for_lecturer(
                connection,
                timetable_entry_id,
                lecturer_id,
            )
            if entry is None:
                raise TimetableEntryNotFoundError()

            geofence_snapshot = _resolve_geofence_snapshot(entry)
            if requires_geofence and geofence_snapshot is None:
                raise ClassroomGeofenceNotConfiguredError(
                    "This timetable entry's classroom has no valid geofence "
                    "(latitude, longitude, and radius) configured."
                )

            await self._repository.create_session(
                connection,
                session_id=session_id,
                course_offering_id=entry.course_offering_id,
                timetable_entry_id=entry.id,
                created_by=user_id,
                session_title=session_title,
                session_type=session_type,
                scheduled_start_at=scheduled_start_at,
                scheduled_end_at=scheduled_end_at,
                check_in_opens_at=resolved_check_in_opens_at,
                check_in_closes_at=resolved_check_in_closes_at,
                late_after_at=resolved_late_after_at,
                requires_face_verification=requires_face_verification,
                requires_geofence=requires_geofence,
                requires_qr=requires_qr,
            )

            enrolled_count = await self._repository.create_session_students_from_enrolments(
                connection,
                session_id,
                entry.course_offering_id,
            )

            if geofence_snapshot is not None:
                centre_latitude, centre_longitude, radius_m = geofence_snapshot
                await self._repository.create_session_geofence(
                    connection,
                    session_id,
                    centre_latitude=centre_latitude,
                    centre_longitude=centre_longitude,
                    radius_m=radius_m,
                    accuracy_buffer_m=DEFAULT_ACCURACY_BUFFER_M,
                    maximum_allowed_accuracy_m=DEFAULT_MAXIMUM_ALLOWED_ACCURACY_M,
                )

            created = await self._repository.find_for_lecturer(connection, session_id, lecturer_id)
            assert created is not None

            await write_audit_log(
                connection,
                actor_user_id=user_id,
                actor_type=ACTOR_TYPE_LECTURER,
                action="session.create",
                entity_type=AUDIT_ENTITY_TYPE,
                entity_id=session_id,
                old_values=None,
                new_values={
                    "courseOfferingId": str(entry.course_offering_id),
                    "timetableEntryId": str(entry.id),
                    "sessionTitle": session_title,
                    "scheduledStartAt": scheduled_start_at.isoformat(),
                    "scheduledEndAt": scheduled_end_at.isoformat(),
                    "requiresFaceVerification": requires_face_verification,
                    "requiresGeofence": requires_geofence,
                    "requiresQr": requires_qr,
                    "enrolledStudentCount": enrolled_count,
                    "geofenceConfigured": geofence_snapshot is not None,
                },
            )

        return created

    async def close_for_user(
        self,
        pool: asyncpg.Pool,
        user_id: UUID,
        session_id: UUID,
    ) -> LecturerSessionRecord:
        async with pool.acquire() as connection, connection.transaction():
            lecturer_id = await self._resolve_active_lecturer_id(connection, user_id)
            record = await self._repository.find_for_lecturer(
                connection,
                session_id,
                lecturer_id,
                lock_for_update=True,
            )
            if record is None:
                raise SessionNotFoundError()
            if record.cancelled_at is not None:
                raise SessionCancelledError()
            if record.closed_at is not None:
                raise SessionAlreadyClosedError()
            if record.activated_at is None:
                raise SessionNotActiveError()

            await self._repository.close(connection, session_id)
            updated = await self._repository.find_for_lecturer(connection, session_id, lecturer_id)
            assert updated is not None

            await write_audit_log(
                connection,
                actor_user_id=user_id,
                actor_type=ACTOR_TYPE_LECTURER,
                action="session.close",
                entity_type=AUDIT_ENTITY_TYPE,
                entity_id=session_id,
                old_values={"closedAt": None},
                new_values={"closedAt": updated.closed_at.isoformat()},
            )

        return updated

    async def list_students_for_user(
        self,
        pool: asyncpg.Pool,
        user_id: UUID,
        session_id: UUID,
    ) -> list[SessionStudentRecord]:
        async with pool.acquire() as connection:
            lecturer_id = await self._resolve_active_lecturer_id(connection, user_id)
            # Confirms the session belongs to this lecturer before returning any
            # student rows — the same ownership check used everywhere else here.
            record = await self._repository.find_for_lecturer(connection, session_id, lecturer_id)
            if record is None:
                raise SessionNotFoundError()

            return await self._repository.list_students_for_session(connection, session_id)

    async def _resolve_active_lecturer_id(
        self,
        connection: asyncpg.Connection,
        user_id: UUID,
    ) -> UUID:
        profile = await self._lecturer_profile_repository.find_by_user_id(connection, user_id)
        if profile is None or profile.profile_status != ACTIVE_PROFILE_STATUS:
            raise LecturerProfileNotFoundError("No active lecturer profile exists for this account.")
        return profile.id


_LATITUDE_RANGE = (Decimal("-90"), Decimal("90"))
_LONGITUDE_RANGE = (Decimal("-180"), Decimal("180"))


def _resolve_geofence_snapshot(
    entry: TimetableEntryForSessionRecord,
) -> tuple[Decimal, Decimal, Decimal] | None:
    """Mirrors the validity check in 0002_add_session_geofence_snapshot.sql's
    backfill, so a freshly created session is snapshotted the same way a
    historical one would have been."""
    latitude = entry.classroom_latitude
    longitude = entry.classroom_longitude
    radius = entry.classroom_default_geofence_radius_m

    if latitude is None or longitude is None or radius is None:
        return None
    if not (_LATITUDE_RANGE[0] <= latitude <= _LATITUDE_RANGE[1]):
        return None
    if not (_LONGITUDE_RANGE[0] <= longitude <= _LONGITUDE_RANGE[1]):
        return None
    if radius <= 0:
        return None

    return latitude, longitude, radius
