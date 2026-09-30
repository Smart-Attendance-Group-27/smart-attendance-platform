import json
from datetime import UTC, datetime
from uuid import UUID

from modules.audit.admin_log.repository import AuditLogRepository

SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
OCCURRED_AT = datetime(2026, 9, 30, 9, 17, tzinfo=UTC)


class RecordingConnection:
    def __init__(self, rows) -> None:
        self.rows = rows
        self.query = ""

    async def fetch(self, query, *args):
        self.query = query
        return self.rows


def build_row(**overrides):
    row = {
        "id": UUID(int=1), "occurred_at": OCCURRED_AT, "actor_user_id": None,
        "actor_type": "system", "actor_name": "System", "action": "session.auto_close",
        "entity_type": "attendance_session", "entity_id": SESSION_ID, "outcome": "success",
        "failure_reason": None, "old_values": None, "new_values": None, "metadata": None,
        "session_course_code": "CS3053", "session_scheduled_start_at": OCCURRED_AT,
    }
    row.update(overrides)
    return row


async def test_structured_values_come_back_as_objects() -> None:
    metadata = {"verificationFactor": "geofence", "affectedStudentCount": 238}
    connection = RecordingConnection([build_row(
        action="session.verification_override",
        old_values=json.dumps({"geofence": "required"}),
        new_values=json.dumps({"geofence": "waived"}),
        metadata=json.dumps(metadata),
    )])

    [record] = await AuditLogRepository().list_audit_logs(connection)

    assert record.old_values == {"geofence": "required"}
    assert record.new_values == {"geofence": "waived"}
    assert record.metadata == metadata


async def test_a_session_entity_is_named_by_its_course() -> None:
    connection = RecordingConnection([build_row()])

    [record] = await AuditLogRepository().list_audit_logs(connection)

    assert record.session_course_code == "CS3053"
    assert record.session_scheduled_start_at == OCCURRED_AT
    assert "log.entity_type = 'attendance_session'" in connection.query
