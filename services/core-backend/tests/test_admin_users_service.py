from uuid import UUID

import pytest

from modules.identity.admin_users.exception import (
    AccountProvisioningError,
    CannotModifyOwnAccountError,
    DuplicateAccountFieldError,
    OrphanedKeycloakUserError,
    UserNotFoundError,
)
from modules.identity.admin_users.repository import UserAccountRecord
from modules.identity.admin_users.schemas import AccountProvisionRequest
from modules.identity.admin_users.service import AdminUserService
from modules.identity.keycloak_admin.exception import KeycloakOperationError

ACTOR_ID = UUID("20000000-0000-0000-0000-000000000001")
TARGET_ID = UUID("20000000-0000-0000-0000-000000000011")


class FakeTransaction:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeConnection:
    def __init__(self):
        self.executions = []

    def transaction(self):
        return FakeTransaction()

    async def execute(self, query, *args):
        self.executions.append((query, args))


class FakeAcquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakePool:
    def __init__(self):
        self.connection = FakeConnection()

    def acquire(self):
        return FakeAcquire(self.connection)


class FakeAdminUserRepository:
    def __init__(self, account: UserAccountRecord | None):
        self.account = account
        self.updated_status: str | None = None

    async def find_user_account(self, connection, user_id, *, lock_for_update=False):
        return self.account

    async def update_account_status(self, connection, user_id, account_status):
        self.updated_status = account_status
        if self.account is not None:
            self.account = UserAccountRecord(
                id=self.account.id,
                account_status=account_status,
                locked_until=self.account.locked_until,
            )


async def test_updates_status_and_writes_audit_log() -> None:
    repository = FakeAdminUserRepository(
        UserAccountRecord(id=TARGET_ID, account_status="active", locked_until=None),
    )
    service = AdminUserService(repository=repository)

    result = await service.update_account_status(FakePool(), ACTOR_ID, TARGET_ID, "suspended")

    assert result.account_status == "suspended"
    assert repository.updated_status == "suspended"


async def test_rejects_self_modification_without_touching_repository() -> None:
    repository = FakeAdminUserRepository(
        UserAccountRecord(id=ACTOR_ID, account_status="active", locked_until=None),
    )
    service = AdminUserService(repository=repository)

    with pytest.raises(CannotModifyOwnAccountError):
        await service.update_account_status(FakePool(), ACTOR_ID, ACTOR_ID, "suspended")

    assert repository.updated_status is None


async def test_rejects_missing_user() -> None:
    repository = FakeAdminUserRepository(None)
    service = AdminUserService(repository=repository)

    with pytest.raises(UserNotFoundError):
        await service.update_account_status(FakePool(), ACTOR_ID, TARGET_ID, "suspended")


class ProvisioningRepository:
    def __init__(self, *, duplicate: str | None = None, fail_database: bool = False):
        self.duplicate = duplicate
        self.fail_database = fail_database
        self.created_user = None
        self.created_profile = None

    async def email_exists(self, connection, email):
        return self.duplicate == "email"

    async def registration_number_exists(self, connection, registration_number):
        return self.duplicate == "registration number"

    async def employee_number_exists(self, connection, employee_number):
        return self.duplicate == "employee number"

    async def create_user(self, connection, **values):
        if self.fail_database:
            raise RuntimeError("database failed")
        self.created_user = values

    async def create_student_profile(self, connection, **values):
        self.created_profile = ("student", values)

    async def create_lecturer_profile(self, connection, **values):
        self.created_profile = ("lecturer", values)

    async def create_administrator_profile(self, connection, **values):
        self.created_profile = ("administrator", values)


class FakeKeycloakClient:
    def __init__(self, *, cleanup_fails: bool = False):
        self.calls = []
        self.cleanup_fails = cleanup_fails

    async def create_user(self, **values):
        self.calls.append(("create", values))
        return "kc-new-user"

    async def assign_realm_role(self, user_id, role_name):
        self.calls.append(("role", user_id, role_name))

    async def set_temporary_password(self, user_id, password):
        self.calls.append(("password", user_id, password))

    async def delete_user(self, user_id):
        self.calls.append(("delete", user_id))
        if self.cleanup_fails:
            raise KeycloakOperationError("delete failed")

    async def disable_user(self, user_id):
        self.calls.append(("disable", user_id))
        if self.cleanup_fails:
            raise KeycloakOperationError("disable failed")


def provision_request(role: str = "student") -> AccountProvisionRequest:
    common = {
        "role": role,
        "email": f"new-{role}@example.test",
        "firstName": "New",
        "middleName": "A",
        "lastName": "User",
        "departmentId": "10000000-0000-0000-0000-000000000001",
    }
    if role == "student":
        common.update(registrationNumber="REG-100", intakeYear=2026, currentSemester=1)
    elif role == "lecturer":
        common.update(employeeNumber="EMP-100", designation="Lecturer")
    else:
        common.update(administrativeScope="faculty")
    return AccountProvisionRequest.model_validate(common)


@pytest.mark.parametrize(
    ("duplicate", "role"),
    [("email", "student"), ("registration number", "student"), ("employee number", "lecturer")],
)
async def test_duplicate_input_never_calls_keycloak(duplicate: str, role: str) -> None:
    repository = ProvisioningRepository(duplicate=duplicate)
    keycloak = FakeKeycloakClient()
    service = AdminUserService(repository=repository, keycloak_client=keycloak)

    with pytest.raises(DuplicateAccountFieldError) as error:
        await service.provision_account(FakePool(), ACTOR_ID, provision_request(role))

    assert error.value.field_name == duplicate
    assert keycloak.calls == []


@pytest.mark.parametrize("role", ["student", "lecturer", "administrator"])
async def test_provisions_linked_user_and_role_profile(role: str) -> None:
    repository = ProvisioningRepository()
    keycloak = FakeKeycloakClient()
    service = AdminUserService(
        repository=repository,
        keycloak_client=keycloak,
        password_factory=lambda: "Generated1!Password",
    )

    result = await service.provision_account(FakePool(), ACTOR_ID, provision_request(role))

    assert result.temporary_password == "Generated1!Password"
    assert result.keycloak_user_id == "kc-new-user"
    assert repository.created_user["keycloak_user_id"] == "kc-new-user"
    assert repository.created_user["email"] == f"new-{role}@example.test"
    assert repository.created_profile[0] == role
    assert ("role", "kc-new-user", role) in keycloak.calls


async def test_database_failure_deletes_keycloak_user_and_returns_controlled_error() -> None:
    repository = ProvisioningRepository(fail_database=True)
    keycloak = FakeKeycloakClient()
    service = AdminUserService(repository=repository, keycloak_client=keycloak)

    with pytest.raises(AccountProvisioningError):
        await service.provision_account(FakePool(), ACTOR_ID, provision_request())

    assert ("delete", "kc-new-user") in keycloak.calls


async def test_compensation_failure_names_orphaned_keycloak_user() -> None:
    repository = ProvisioningRepository(fail_database=True)
    keycloak = FakeKeycloakClient(cleanup_fails=True)
    service = AdminUserService(repository=repository, keycloak_client=keycloak)

    with pytest.raises(OrphanedKeycloakUserError) as error:
        await service.provision_account(FakePool(), ACTOR_ID, provision_request())

    assert error.value.keycloak_user_id == "kc-new-user"
    assert "kc-new-user" in str(error.value)
    assert ("disable", "kc-new-user") in keycloak.calls


async def test_generated_password_is_never_logged_or_audited(caplog) -> None:
    password = "NeverLogThis1!"
    pool = FakePool()
    service = AdminUserService(
        repository=ProvisioningRepository(fail_database=True),
        keycloak_client=FakeKeycloakClient(),
        password_factory=lambda: password,
    )

    with pytest.raises(AccountProvisioningError):
        await service.provision_account(pool, ACTOR_ID, provision_request())

    assert password not in caplog.text
    assert password not in repr(pool.connection.executions)
