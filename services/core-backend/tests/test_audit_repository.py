import json
from typing import Any
from uuid import UUID

from modules.audit.repository import FAILURE_OUTCOME, SUCCESS_OUTCOME, write_audit_log

ACTOR_ID = UUID("20000000-0000-0000-0000-000000000002")
ENTITY_ID = UUID("40000000-0000-0000-0000-000000000001")


class FakeConnection:
    def __init__(self) -> None:
        self.query = ""
        self.args: tuple[Any, ...] = ()

    async def execute(self, query: str, *args: Any) -> None:
        self.query = query
        self.args = args


async def test_writes_actor_action_and_entity_with_source_service() -> None:
    connection = FakeConnection()

    await write_audit_log(
        connection,
        actor_user_id=ACTOR_ID,
        actor_type="lecturer",
        action="manual_review.decide",
        entity_type="verification_attempt",
        entity_id=ENTITY_ID,
    )

    assert "audit.audit_logs" in connection.query
    assert connection.args[0] == ACTOR_ID
    assert connection.args[1] == "lecturer"
    assert connection.args[2] == "manual_review.decide"
    assert connection.args[3] == "verification_attempt"
    assert connection.args[4] == ENTITY_ID
    assert connection.args[5] == SUCCESS_OUTCOME


async def test_serializes_old_and_new_values_as_json() -> None:
    connection = FakeConnection()

    await write_audit_log(
        connection,
        actor_user_id=ACTOR_ID,
        actor_type="lecturer",
        action="manual_review.decide",
        entity_type="verification_attempt",
        entity_id=ENTITY_ID,
        old_values={"reviewStatus": None},
        new_values={"reviewStatus": "approve"},
        metadata={"sessionId": "abc"},
    )

    old_values, new_values, metadata = connection.args[7], connection.args[8], connection.args[9]
    assert json.loads(old_values) == {"reviewStatus": None}
    assert json.loads(new_values) == {"reviewStatus": "approve"}
    assert json.loads(metadata) == {"sessionId": "abc"}


async def test_leaves_values_null_when_not_provided() -> None:
    connection = FakeConnection()

    await write_audit_log(
        connection,
        actor_user_id=ACTOR_ID,
        actor_type="lecturer",
        action="session.activate",
        entity_type="attendance_session",
        entity_id=ENTITY_ID,
        outcome=FAILURE_OUTCOME,
        failure_reason="already active",
    )

    assert connection.args[5] == FAILURE_OUTCOME
    assert connection.args[6] == "already active"
    assert connection.args[7] is None
    assert connection.args[8] is None
    assert connection.args[9] is None


async def test_a_system_action_has_no_actor_user() -> None:
    connection = FakeConnection()

    await write_audit_log(
        connection,
        actor_user_id=None,
        actor_type="system",
        action="session.auto_close",
        entity_type="attendance_session",
        entity_id=ENTITY_ID,
        new_values={"reason": "Scheduled end plus grace period exceeded"},
    )

    assert connection.args[0] is None
    assert connection.args[1] == "system"
    assert json.loads(connection.args[8]) == {"reason": "Scheduled end plus grace period exceeded"}
