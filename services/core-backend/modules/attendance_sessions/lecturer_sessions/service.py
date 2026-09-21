import asyncio
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import asyncpg

from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.academic.lecturer_profile.repository import LecturerProfileRepository
from modules.attendance_sessions.lecturer_sessions.exception import (
    ClassroomGeofenceNotConfiguredError,
    GeofenceRequiredError,
    InvalidCancellationReasonError,
    InvalidSessionScheduleError,
    SessionAlreadyActiveError,
    SessionAlreadyCancelledError,
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
from modules.attendance_sessions.qr_session.cache import QrBatchMetadataCache
from modules.attendance_sessions.qr_session.repository import QrSessionRepository
from modules.attendance_verification.check_in.service import CheckInService
from modules.attendance_verification.finalization.repository import FinalizationRepository
from modules.attendance_verification.finalization.service import AttendanceFinalizationService
from modules.attendance_verification.finalization.types import FinalizationSummary
from modules.audit.repository import write_audit_log
from modules.contracts.announce import announce
from modules.contracts.attendance_policy import (
    AttendancePolicyProvider,
    DefaultAttendancePolicyProvider,
)
from modules.contracts.notifications import NoOpNotificationProducer, NotificationProducer
from modules.contracts.qr_evidence import QrEvidenceProvider
from modules.notification.push.notification_service import NotificationService
from modules.notification.push.provider import PushProvider

ACTIVE_PROFILE_STATUS = "active"
ACTOR_TYPE_LECTURER = "lecturer"
AUDIT_ENTITY_TYPE = "attendance_session"

# Same demo/seed defaults used for the one hand-seeded session
# (database/smart_attendance_seed.sql) — no per-session UI for these yet.
DEFAULT_ACCURACY_BUFFER_M = Decimal("10")
DEFAULT_MAXIMUM_ALLOWED_ACCURACY_M = Decimal("50")
DEFAULT_LATE_AFTER_MINUTES = 10
MIN_CANCELLATION_REASON_LENGTH = 3
MAX_CANCELLATION_REASON_LENGTH = 500


class LecturerSessionService:
    def __init__(
        self,
        repository: LecturerSessionRepository | None = None,
        lecturer_profile_repository: LecturerProfileRepository | None = None,
        qr_evidence: QrEvidenceProvider | None = None,
        qr_session_repository: QrSessionRepository | None = None,
        check_in_service: CheckInService | None = None,
        notification_service: NotificationService | None = None,
        notification_producer: NotificationProducer | None = None,
        finalization_repository: FinalizationRepository | None = None,
        attendance_policy: AttendancePolicyProvider | None = None,
    ) -> None:
        self._repository = repository or LecturerSessionRepository()
        self._lecturer_profile_repository = (
            lecturer_profile_repository or LecturerProfileRepository()
        )
        self._qr_evidence = qr_evidence
        self._qr_session_repository = qr_session_repository or QrSessionRepository()
        self._check_in_service = check_in_service or CheckInService()
        self._notification_service = notification_service
        self._notification_producer = notification_producer or NoOpNotificationProducer()
        self._finalization_repository = finalization_repository
        self._attendance_policy = attendance_policy or DefaultAttendancePolicyProvider()

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

            await announce(
                connection,
                lambda: self._notification_producer.session_opened(
                    connection,
                    session_id=session_id,
                ),
                label="session_opened",
            )

        # Fire push notifications to all enrolled students.
        # This runs AFTER the transaction commits so the session row is visible.
        if self._notification_service is not None:
            asyncio.create_task(
                _notify_enrolled_students(
                    pool=pool,
                    session_id=session_id,
                    session_record=updated,
                    notification_service=self._notification_service,
                )
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
        # Geofence is the only step that creates a verification attempt, so a
        # session without it could never be attended.
        if not requires_geofence:
            raise GeofenceRequiredError()

        if scheduled_end_at <= scheduled_start_at:
            raise InvalidSessionScheduleError("scheduledEndAt must be after scheduledStartAt.")

        session_id = uuid4()

        async with pool.acquire() as connection, connection.transaction():
            (
                resolved_check_in_opens_at,
                resolved_check_in_closes_at,
                resolved_late_after_at,
            ) = await self._resolve_check_in_times(
                connection,
                scheduled_start_at=scheduled_start_at,
                scheduled_end_at=scheduled_end_at,
                check_in_opens_at=check_in_opens_at,
                check_in_closes_at=check_in_closes_at,
                late_after_at=late_after_at,
            )

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
        redis_client=None,
    ) -> tuple[LecturerSessionRecord, FinalizationSummary | None]:
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
            closed_at = updated.closed_at
            assert closed_at is not None

            deactivated_qr_batch_ids = (
                await self._qr_session_repository.close_existing_active_qr_sessions(
                    connection,
                    session_id,
                    closed_at,
                )
            )

            summary: FinalizationSummary | None = None
            if self._qr_evidence is not None:
                finalization_service = AttendanceFinalizationService(
                    self._qr_evidence,
                    self._check_in_service,
                    self._finalization_repository,
                )
                summary = await finalization_service.finalize(
                    connection,
                    session_id=session_id,
                    closed_at=closed_at,
                    actor_user_id=user_id,
                )
                summary = replace(
                    summary,
                    deactivated_qr_batch_ids=tuple(deactivated_qr_batch_ids),
                )

            if summary is not None:
                await self._announce_finalization(connection, session_id, summary)

            audit_new_values: dict[str, object] = {"closedAt": closed_at.isoformat()}
            if summary is not None:
                audit_new_values["finalization"] = {
                    "present": summary.present,
                    "late": summary.late,
                    "absent": summary.absent,
                    "keptManual": summary.kept_manual,
                    "reconciled": len(summary.reconciled_student_ids),
                    "deactivatedQrBatches": len(summary.deactivated_qr_batch_ids),
                }

            await write_audit_log(
                connection,
                actor_user_id=user_id,
                actor_type=ACTOR_TYPE_LECTURER,
                action="session.close",
                entity_type=AUDIT_ENTITY_TYPE,
                entity_id=session_id,
                old_values={"closedAt": None},
                new_values=audit_new_values,
            )

        if summary is not None:
            await AttendanceFinalizationService.after_commit(summary, redis_client)

        return updated, summary

    async def cancel_for_user(
        self,
        pool: asyncpg.Pool,
        user_id: UUID,
        session_id: UUID,
        reason: str,
        redis_client=None,
    ) -> LecturerSessionRecord:
        reason = reason.strip()
        if not MIN_CANCELLATION_REASON_LENGTH <= len(reason) <= MAX_CANCELLATION_REASON_LENGTH:
            raise InvalidCancellationReasonError()

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
                raise SessionAlreadyCancelledError()
            if record.closed_at is not None:
                raise SessionAlreadyClosedError()

            await self._repository.cancel(connection, session_id, reason)
            updated = await self._repository.find_for_lecturer(connection, session_id, lecturer_id)
            assert updated is not None
            cancelled_at = updated.cancelled_at
            assert cancelled_at is not None

            # No attendance records are written: a cancelled session has no
            # attendance to decide.
            deactivated_qr_batch_ids = (
                await self._qr_session_repository.close_existing_active_qr_sessions(
                    connection,
                    session_id,
                    cancelled_at,
                )
            )

            await write_audit_log(
                connection,
                actor_user_id=user_id,
                actor_type=ACTOR_TYPE_LECTURER,
                action="session.cancel",
                entity_type=AUDIT_ENTITY_TYPE,
                entity_id=session_id,
                old_values={"cancelledAt": None},
                new_values={
                    "cancelledAt": cancelled_at.isoformat(),
                    "reason": reason,
                    "deactivatedQrBatches": len(deactivated_qr_batch_ids),
                },
            )

        cache = QrBatchMetadataCache(redis_client)
        for batch_id in deactivated_qr_batch_ids:
            await cache.delete_qr_batch_cache(batch_id)

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

            students = await self._repository.list_students_for_session(connection, session_id)

            if self._qr_evidence is None:
                return students

            progress = await self._qr_evidence.progress_for_session(connection, session_id)
            return [
                replace(
                    student,
                    qr_required_count=progress[student.verification_attempt_id].required_count,
                    qr_passed_count=progress[student.verification_attempt_id].passed_count,
                )
                if student.verification_attempt_id in progress
                else student
                for student in students
            ]

    async def _announce_finalization(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
        summary: FinalizationSummary,
    ) -> None:
        # Only the automatic decisions: a student whose attendance a lecturer
        # set by hand was already told when that happened.
        results = [
            (result.student_user_id, result.status)
            for result in summary.results
            if result.student_user_id is not None
        ]
        if not results:
            return

        await announce(
            connection,
            lambda: self._notification_producer.attendance_finalized(
                connection,
                session_id=session_id,
                results=results,
            ),
            label="attendance_finalized",
        )

    async def _resolve_check_in_times(
        self,
        connection: asyncpg.Connection,
        *,
        scheduled_start_at: datetime,
        scheduled_end_at: datetime,
        check_in_opens_at: datetime | None,
        check_in_closes_at: datetime | None,
        late_after_at: datetime | None,
    ) -> tuple[datetime, datetime, datetime]:
        """Fills in the check-in times a request left out.

        A value in the request always wins. What is left comes from the active
        attendance policy, and from the built-in defaults when there is none.
        """

        opens = check_in_opens_at or scheduled_start_at

        # Nothing to look up when the request already says everything.
        policy = None
        if check_in_closes_at is None or late_after_at is None:
            policy = await self._attendance_policy.get_active(connection)

        if check_in_closes_at is not None:
            closes = check_in_closes_at
        elif policy is not None:
            closes = min(
                opens + timedelta(minutes=policy.check_in_window_minutes),
                scheduled_end_at,
            )
        else:
            closes = scheduled_end_at

        if late_after_at is not None:
            late_after = late_after_at
        elif policy is not None:
            late_after = min(
                scheduled_start_at + timedelta(minutes=policy.late_threshold_minutes),
                closes,
            )
        else:
            late_after = scheduled_start_at + timedelta(minutes=DEFAULT_LATE_AFTER_MINUTES)

        if closes <= opens:
            raise InvalidSessionScheduleError("checkInClosesAt must be after checkInOpensAt.")
        if not (opens <= late_after <= closes):
            raise InvalidSessionScheduleError(
                "lateAfterAt must fall between checkInOpensAt and checkInClosesAt."
            )

        return opens, closes, late_after

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


# ---------------------------------------------------------------------------
# Notification helpers
# ---------------------------------------------------------------------------


async def _fetch_enrolled_user_ids(
    pool: asyncpg.Pool,
    session_id: UUID,
) -> list[UUID]:
    """Return identity.users.id for every student enrolled in this session."""
    async with pool.acquire() as connection:
        rows = await connection.fetch(
            """
            SELECT sp.user_id
            FROM attendance_session.session_students AS ss
            JOIN academic.student_profiles AS sp ON sp.id = ss.student_id
            WHERE ss.session_id = $1
            """,
            session_id,
        )
    return [row["user_id"] for row in rows]


async def _notify_enrolled_students(
    *,
    pool: asyncpg.Pool,
    session_id: UUID,
    session_record: LecturerSessionRecord,
    notification_service: NotificationService,
) -> None:
    """Send ATTENDANCE_SESSION_OPENED push to every enrolled student.

    Runs as a fire-and-forget background task after the activation
    transaction commits.  Failures are logged but never re-raised so they
    cannot affect the session activation response.
    """
    import logging

    logger = logging.getLogger(__name__)

    try:
        user_ids = await _fetch_enrolled_user_ids(pool, session_id)
    except Exception:
        logger.exception(
            "Failed to fetch enrolled students for session=%s; "
            "push notifications will not be sent.",
            session_id,
        )
        return

    course_name = session_record.course_name or "your course"
    title = "Attendance Session Open"
    body = f"An attendance session for {course_name} is now open. Check in now."

    for user_id in user_ids:
        try:
            await notification_service.send_notification(
                pool,
                recipient_user_id=user_id,
                notification_type="ATTENDANCE_SESSION_OPENED",
                title=title,
                body=body,
                priority="high",
                related_entity_type="ATTENDANCE_SESSION",
                related_entity_id=session_id,
                in_app_visible=True,
                extra_data={"sessionId": str(session_id)},
            )
        except Exception:
            logger.exception(
                "Failed to send session-opened notification to user=%s "
                "for session=%s.",
                user_id,
                session_id,
            )
