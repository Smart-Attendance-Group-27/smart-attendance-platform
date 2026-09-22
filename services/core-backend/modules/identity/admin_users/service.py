import logging
import secrets
import string
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

import asyncpg

from modules.audit.repository import FAILURE_OUTCOME, write_audit_log
from modules.identity.admin_users.exception import (
    AccountProvisioningError,
    AccountProvisioningUnavailableError,
    CannotModifyOwnAccountError,
    DuplicateAccountFieldError,
    OrphanedKeycloakUserError,
    UserNotFoundError,
)
from modules.identity.admin_users.repository import (
    AdministratorAccountRecord,
    AdminUserRepository,
    DepartmentOptionRecord,
    LecturerAccountRecord,
    StudentAccountRecord,
    UserAccountRecord,
)
from modules.identity.admin_users.schemas import AccountProvisionRequest, ProvisionedAccountRole
from modules.identity.keycloak_admin.exception import (
    KeycloakAdminError,
    KeycloakUnavailableError,
    KeycloakUserAlreadyExistsError,
)

ACTOR_TYPE_ADMINISTRATOR = "administrator"
AUDIT_ENTITY_TYPE = "user_account"
logger = logging.getLogger(__name__)


class KeycloakProvisioningClient(Protocol):
    async def create_user(self, *, email: str, first_name: str, last_name: str) -> str: ...

    async def assign_realm_role(self, user_id: str, role_name: str) -> None: ...

    async def set_temporary_password(self, user_id: str, password: str) -> None: ...

    async def delete_user(self, user_id: str) -> None: ...

    async def disable_user(self, user_id: str) -> None: ...


@dataclass(frozen=True)
class UserDirectory:
    students: list[StudentAccountRecord]
    lecturers: list[LecturerAccountRecord]
    administrators: list[AdministratorAccountRecord]


@dataclass(frozen=True)
class ProvisionedAccount:
    user_id: UUID
    keycloak_user_id: str
    role: ProvisionedAccountRole
    email: str
    temporary_password: str


def generate_temporary_password() -> str:
    """Generate a 16-character password containing all common character classes."""
    random = secrets.SystemRandom()
    required = [
        random.choice(string.ascii_uppercase),
        random.choice(string.ascii_lowercase),
        random.choice(string.digits),
        random.choice("!@#$%^&*"),
    ]
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    characters = required + [random.choice(alphabet) for _ in range(12)]
    random.shuffle(characters)
    return "".join(characters)


class AdminUserService:
    def __init__(
        self,
        repository: AdminUserRepository | None = None,
        *,
        keycloak_client: KeycloakProvisioningClient | None = None,
        password_factory: Callable[[], str] = generate_temporary_password,
    ) -> None:
        self._repository = repository or AdminUserRepository()
        self._keycloak_client = keycloak_client
        self._password_factory = password_factory

    async def get_directory(self, pool: asyncpg.Pool) -> UserDirectory:
        async with pool.acquire() as connection:
            students = await self._repository.list_students(connection)
            lecturers = await self._repository.list_lecturers(connection)
            administrators = await self._repository.list_administrators(connection)
        return UserDirectory(students=students, lecturers=lecturers, administrators=administrators)

    async def get_provisioning_departments(
        self,
        pool: asyncpg.Pool,
    ) -> list[DepartmentOptionRecord]:
        async with pool.acquire() as connection:
            return await self._repository.list_active_departments(connection)

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

    async def provision_account(
        self,
        pool: asyncpg.Pool,
        actor_user_id: UUID,
        request: AccountProvisionRequest,
    ) -> ProvisionedAccount:
        if self._keycloak_client is None:
            raise AccountProvisioningUnavailableError()

        user_id = uuid4()
        try:
            await self._validate_unique_fields(pool, request)
        except DuplicateAccountFieldError:
            await self._audit_failure(pool, actor_user_id, user_id, request, "duplicate_input")
            raise

        temporary_password = self._password_factory()
        keycloak_user_id: str | None = None

        try:
            keycloak_user_id = await self._keycloak_client.create_user(
                email=request.email,
                first_name=request.first_name,
                last_name=request.last_name,
            )
            await self._keycloak_client.assign_realm_role(
                keycloak_user_id,
                request.role.value,
            )
            await self._keycloak_client.set_temporary_password(
                keycloak_user_id,
                temporary_password,
            )
        except KeycloakUserAlreadyExistsError as error:
            await self._audit_failure(pool, actor_user_id, user_id, request, "keycloak_duplicate")
            raise DuplicateAccountFieldError("email") from error
        except KeycloakAdminError as error:
            if keycloak_user_id is not None:
                await self._compensate_or_raise(
                    pool, actor_user_id, user_id, request, keycloak_user_id, "keycloak_setup_failed",
                )
            else:
                await self._audit_failure(
                    pool, actor_user_id, user_id, request, "keycloak_create_failed",
                )
            if isinstance(error, KeycloakUnavailableError):
                raise AccountProvisioningUnavailableError() from error
            raise AccountProvisioningError() from error

        assert keycloak_user_id is not None
        try:
            async with pool.acquire() as connection, connection.transaction():
                await self._repository.create_user(
                    connection,
                    user_id=user_id,
                    email=request.email,
                    keycloak_user_id=keycloak_user_id,
                    created_by=actor_user_id,
                )
                await self._create_profile(connection, user_id, request)
                await write_audit_log(
                    connection,
                    actor_user_id=actor_user_id,
                    actor_type=ACTOR_TYPE_ADMINISTRATOR,
                    action="user_account.provision",
                    entity_type=AUDIT_ENTITY_TYPE,
                    entity_id=user_id,
                    new_values={"email": request.email, "role": request.role.value},
                    metadata={"keycloakUserId": keycloak_user_id},
                )
        except Exception as error:
            await self._compensate_or_raise(
                pool, actor_user_id, user_id, request, keycloak_user_id, "database_write_failed",
            )
            raise AccountProvisioningError() from error

        return ProvisionedAccount(
            user_id=user_id,
            keycloak_user_id=keycloak_user_id,
            role=request.role,
            email=request.email,
            temporary_password=temporary_password,
        )

    async def _validate_unique_fields(
        self,
        pool: asyncpg.Pool,
        request: AccountProvisionRequest,
    ) -> None:
        async with pool.acquire() as connection:
            if await self._repository.email_exists(connection, request.email):
                raise DuplicateAccountFieldError("email")
            if (
                request.registration_number
                and await self._repository.registration_number_exists(
                    connection,
                    request.registration_number,
                )
            ):
                raise DuplicateAccountFieldError("registration number")
            if (
                request.employee_number
                and await self._repository.employee_number_exists(
                    connection,
                    request.employee_number,
                )
            ):
                raise DuplicateAccountFieldError("employee number")

    async def _create_profile(
        self,
        connection: asyncpg.Connection,
        user_id: UUID,
        request: AccountProvisionRequest,
    ) -> None:
        common = {
            "profile_id": uuid4(),
            "user_id": user_id,
            "first_name": request.first_name,
            "middle_name": request.middle_name,
            "last_name": request.last_name,
            "department_id": request.department_id,
        }
        if request.role is ProvisionedAccountRole.STUDENT:
            assert request.registration_number is not None
            assert request.intake_year is not None
            assert request.current_semester is not None
            await self._repository.create_student_profile(
                connection,
                registration_number=request.registration_number,
                intake_year=request.intake_year,
                current_semester=request.current_semester,
                **common,
            )
        elif request.role is ProvisionedAccountRole.LECTURER:
            assert request.employee_number is not None
            assert request.designation is not None
            await self._repository.create_lecturer_profile(
                connection,
                employee_number=request.employee_number,
                designation=request.designation,
                **common,
            )
        else:
            assert request.administrative_scope is not None
            await self._repository.create_administrator_profile(
                connection,
                administrative_scope=request.administrative_scope,
                **common,
            )

    async def _compensate_or_raise(
        self,
        pool: asyncpg.Pool,
        actor_user_id: UUID,
        user_id: UUID,
        request: AccountProvisionRequest,
        keycloak_user_id: str,
        reason: str,
    ) -> None:
        assert self._keycloak_client is not None
        compensation = "deleted"
        try:
            await self._keycloak_client.delete_user(keycloak_user_id)
        except KeycloakAdminError:
            compensation = "disabled"
            try:
                await self._keycloak_client.disable_user(keycloak_user_id)
            except KeycloakAdminError as compensation_error:
                logger.error(
                    "Account provisioning compensation failed for Keycloak user %s",
                    keycloak_user_id,
                )
                await self._audit_failure(
                    pool,
                    actor_user_id,
                    user_id,
                    request,
                    reason,
                    keycloak_user_id=keycloak_user_id,
                    compensation="failed",
                )
                raise OrphanedKeycloakUserError(keycloak_user_id) from compensation_error

        await self._audit_failure(
            pool,
            actor_user_id,
            user_id,
            request,
            reason,
            keycloak_user_id=keycloak_user_id,
            compensation=compensation,
        )

    async def _audit_failure(
        self,
        pool: asyncpg.Pool,
        actor_user_id: UUID,
        user_id: UUID,
        request: AccountProvisionRequest,
        reason: str,
        *,
        keycloak_user_id: str | None = None,
        compensation: str | None = None,
    ) -> None:
        try:
            async with pool.acquire() as connection, connection.transaction():
                await write_audit_log(
                    connection,
                    actor_user_id=actor_user_id,
                    actor_type=ACTOR_TYPE_ADMINISTRATOR,
                    action="user_account.provision",
                    entity_type=AUDIT_ENTITY_TYPE,
                    entity_id=user_id,
                    outcome=FAILURE_OUTCOME,
                    failure_reason=reason,
                    new_values={"email": request.email, "role": request.role.value},
                    metadata={
                        "keycloakUserId": keycloak_user_id,
                        "compensation": compensation,
                    },
                )
        except Exception:
            logger.exception("Could not write account provisioning failure audit")
