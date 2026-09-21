"""Route tests for /api/v1/students/me/notifications read model."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from conftest import (
    LINKED_STUDENT_SUBJECT,
    FakePool,
    build_authentication_service_for_tests,
    build_settings,
    default_connection,
)
from main import create_app
from modules.identity.auth.dependencies import get_authentication_service
from modules.notification.student_notifications.route import (
    get_student_notification_service,
)
from modules.notification.student_notifications.service import (
    StudentNotification,
    StudentNotificationService,
    _map_notification_type,
)

NOTIFICATIONS_URL = "/api/v1/students/me/notifications"


def authorize(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class StubStudentNotificationService:
    def __init__(self, notifications=None, mark_result=True):
        self.notifications = notifications or []
        self.mark_result = mark_result

    async def list_for_user(self, pool, user_id):
        return self.notifications

    async def mark_as_read(self, pool, *, user_id, notification_id):
        return self.mark_result


def make_client(jwks_document, stub_service):
    app = create_app(enable_database=False)
    pool = FakePool(default_connection())
    app.state.db_pool = pool
    app.state.settings = build_settings()

    auth_service = build_authentication_service_for_tests(jwks_document)
    app.dependency_overrides[get_authentication_service] = lambda: auth_service
    app.dependency_overrides[get_student_notification_service] = lambda: stub_service
    return TestClient(app, raise_server_exceptions=False)


def test_list_notifications_requires_auth(jwks_document):
    client = make_client(jwks_document, StubStudentNotificationService())
    response = client.get(NOTIFICATIONS_URL)
    assert response.status_code == 401


def test_list_notifications_returns_code_and_related_entity_type(
    jwks_document, make_access_token
):
    notif_id = uuid4()
    session_id = uuid4()
    created_at = datetime(2026, 9, 21, 12, 0, 0, tzinfo=UTC)

    sample_item = StudentNotification(
        id=notif_id,
        title="Session Cancelled",
        message="Your class was cancelled",
        type="general",
        code="ATTENDANCE_SESSION_CANCELLED",
        created_at=created_at,
        is_read=False,
        related_id=session_id,
        related_entity_type="ATTENDANCE_SESSION",
    )

    stub = StubStudentNotificationService(notifications=[sample_item])
    client = make_client(jwks_document, stub)
    token = make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))

    response = client.get(NOTIFICATIONS_URL, headers=authorize(token))
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(notif_id)
    assert data[0]["title"] == "Session Cancelled"
    assert data[0]["type"] == "general"
    assert data[0]["code"] == "ATTENDANCE_SESSION_CANCELLED"
    assert data[0]["relatedId"] == str(session_id)
    assert data[0]["relatedEntityType"] == "ATTENDANCE_SESSION"
    assert data[0]["isRead"] is False


def test_map_notification_type():
    assert _map_notification_type("QR_SESSION_ACTIVE") == "qr_session"
    assert _map_notification_type("QR_REQUIRED") == "qr_session"
    assert _map_notification_type("ATTENDANCE_SESSION_OPENED") == "attendance"
    assert _map_notification_type("ATTENDANCE_SESSION_STARTED") == "attendance"
    assert _map_notification_type("UPCOMING_CLASS") == "attendance"
    assert _map_notification_type("ATTENDANCE_RESULT") == "attendance_update"
    assert _map_notification_type("ATTENDANCE_SESSION_CANCELLED") == "general"
    assert _map_notification_type("ATTENDANCE_RISK") == "general"
    assert _map_notification_type("GENERAL") == "general"
    assert _map_notification_type(None) == "general"


def test_mark_as_read_success(jwks_document, make_access_token):
    notif_id = uuid4()
    stub = StubStudentNotificationService(mark_result=True)
    client = make_client(jwks_document, stub)
    token = make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))

    response = client.post(
        f"{NOTIFICATIONS_URL}/{notif_id}/read", headers=authorize(token)
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_mark_as_read_not_found(jwks_document, make_access_token):
    notif_id = uuid4()
    stub = StubStudentNotificationService(mark_result=False)
    client = make_client(jwks_document, stub)
    token = make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))

    response = client.post(
        f"{NOTIFICATIONS_URL}/{notif_id}/read", headers=authorize(token)
    )
    assert response.status_code == 404
