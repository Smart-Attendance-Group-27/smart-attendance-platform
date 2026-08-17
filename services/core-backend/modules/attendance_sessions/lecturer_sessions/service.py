from uuid import UUID

import asyncpg

from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.academic.lecturer_profile.repository import LecturerProfileRepository
from modules.attendance_sessions.lecturer_sessions.exception import (
    SessionAlreadyActiveError,
    SessionAlreadyClosedError,
    SessionCancelledError,
    SessionNotActiveError,
    SessionNotFoundError,
)
from modules.attendance_sessions.lecturer_sessions.repository import (
    LecturerSessionRecord,
    LecturerSessionRepository,
    SessionStudentRecord,
)
from modules.audit.repository import write_audit_log

ACTIVE_PROFILE_STATUS = "active"
ACTOR_TYPE_LECTURER = "lecturer"
AUDIT_ENTITY_TYPE = "attendance_session"


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
