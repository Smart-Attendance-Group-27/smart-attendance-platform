import logging

from modules.contracts.announce import announce


class FakeTransaction:
    def __init__(self, connection: "FakeConnection") -> None:
        self.connection = connection

    async def __aenter__(self) -> None:
        self.connection.open_savepoints += 1

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        self.connection.open_savepoints -= 1
        if exc_type is not None:
            self.connection.rolled_back += 1
        # Never swallows: like a real savepoint, it rolls back and re-raises.
        return False


class FakeConnection:
    def __init__(self) -> None:
        self.open_savepoints = 0
        self.rolled_back = 0

    def transaction(self) -> FakeTransaction:
        return FakeTransaction(self)


async def test_runs_the_call_inside_a_savepoint() -> None:
    connection = FakeConnection()
    seen: list[int] = []

    async def notification() -> None:
        seen.append(connection.open_savepoints)

    await announce(connection, notification, label="session_opened")

    assert seen == [1]
    assert connection.open_savepoints == 0
    assert connection.rolled_back == 0


async def test_a_failing_call_is_swallowed_and_only_the_savepoint_rolls_back(caplog) -> None:
    connection = FakeConnection()

    async def notification() -> None:
        raise RuntimeError("notification store unavailable")

    with caplog.at_level(logging.ERROR):
        await announce(connection, notification, label="attendance_finalized")

    assert connection.rolled_back == 1
    assert "attendance_finalized" in caplog.text
    assert "notification store unavailable" in caplog.text


async def test_the_call_is_not_started_until_the_savepoint_is_open() -> None:
    connection = FakeConnection()
    started_inside_savepoint: list[bool] = []

    def notification():
        started_inside_savepoint.append(connection.open_savepoints == 1)

        async def run() -> None:
            return None

        return run()

    await announce(connection, notification, label="session_opened")

    assert started_inside_savepoint == [True]
