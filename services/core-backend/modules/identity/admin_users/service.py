from dataclasses import dataclass
from uuid import UUID

import asyncpg

from modules.identity.admin_users.exception import (
    CannotModifyOwnAccountError,
    UserNotFoundError,
)
from modules.identity.admin_users.repository import (
    AdministratorAccountRecord,
    AdminUserRepository,
    LecturerAccountRecord,
    StudentAccountRecord,
    UserAccountRecord,
)
from modules.audit.repository import write_audit_log

ACTOR_TYPE_ADMINISTRATOR = "administrator"
AUDIT_ENTITY_TYPE = "user_account"


@dataclass(frozen=True)
class UserDirectory:
    students: list[StudentAccountRecord]
    lecturers: list[LecturerAccountRecord]
    administrators: list[AdministratorAccountRecord]


class AdminUserService:
    def __init__(self, repository: AdminUserRepository | None = None) -> None:
        self._repository = repository or AdminUserRepository()

    async def get_directory(self, pool: asyncpg.Pool) -> UserDirectory:
        async with pool.acquire() as connection:
            students = await self._repository.list_students(connection)
            lecturers = await self._repository.list_lecturers(connection)
            administrators = await self._repository.list_administrators(connection)
        return UserDirectory(students=students, lecturers=lecturers, administrators=administrators)

    async def update_account_status(
        self,
        pool: asyncpg.Pool,
        actor_user_id: UUID,
        target_user_id: UUID,
        account_status: str,
    ) -> UserAccountRecord:
        if actor_user_id == target_user_id:
            raise CannotModifyOwnAccountError()

        async with pool.acquire() as connection, connection.transaction():
            before = await self._repository.find_user_account(
                connection,
                target_user_id,
                lock_for_update=True,
            )
            if before is None:
                raise UserNotFoundError()

            await self._repository.update_account_status(connection, target_user_id, account_status)
            after = await self._repository.find_user_account(connection, target_user_id)
            assert after is not None

            await write_audit_log(
                connection,
                actor_user_id=actor_user_id,
                actor_type=ACTOR_TYPE_ADMINISTRATOR,
                action="user_account.set_status",
                entity_type=AUDIT_ENTITY_TYPE,
                entity_id=target_user_id,
                old_values={"accountStatus": before.account_status},
                new_values={"accountStatus": after.account_status},
            )

        return after
