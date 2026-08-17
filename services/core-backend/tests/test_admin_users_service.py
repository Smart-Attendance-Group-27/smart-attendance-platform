from uuid import UUID

import pytest

from modules.identity.admin_users.exception import (
    CannotModifyOwnAccountError,
    UserNotFoundError,
)
from modules.identity.admin_users.repository import UserAccountRecord
from modules.identity.admin_users.service import AdminUserService

ACTOR_ID = UUID("20000000-0000-0000-0000-000000000001")
TARGET_ID = UUID("20000000-0000-0000-0000-000000000011")


class FakeTransaction:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeConnection:
    def transaction(self):
        return FakeTransaction()

    async def execute(self, query, *args):
        pass


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
