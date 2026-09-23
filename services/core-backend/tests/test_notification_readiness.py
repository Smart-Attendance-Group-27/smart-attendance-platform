from contextlib import AbstractAsyncContextManager

from modules.notification.readiness import check_notification_schema_readiness


class Transaction(AbstractAsyncContextManager):
    def __init__(self) -> None:
        self.readonly = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class Connection:
    def __init__(self, row: dict[str, bool]) -> None:
        self.row = row
        self.transaction_options: dict[str, bool] = {}
        self.query = ""

    def transaction(self, **options):
        self.transaction_options = options
        return Transaction()

    async def fetchrow(self, query: str):
        self.query = query
        return self.row


class Acquire(AbstractAsyncContextManager):
    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class Pool:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def acquire(self):
        return Acquire(self.connection)


async def test_notification_schema_preflight_checks_both_required_objects_read_only() -> None:
    connection = Connection(
        {"push_worker_ready": True, "reminder_scheduler_ready": False},
    )

    result = await check_notification_schema_readiness(Pool(connection))  # type: ignore[arg-type]

    assert result.push_worker_ready is True
    assert result.reminder_scheduler_ready is False
    assert connection.transaction_options == {"readonly": True}
    assert "information_schema.columns" in connection.query
    assert "pg_indexes" in connection.query
    assert "next_attempt_at" in connection.query
    assert "uq_notifications_upcoming_class_session_user" in connection.query
