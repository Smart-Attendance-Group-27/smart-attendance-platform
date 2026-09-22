from unittest.mock import AsyncMock
from uuid import uuid4

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
from modules.notification.preferences.repository import NotificationPreferenceRecord
from modules.notification.preferences.route import get_notification_preferences_service

URL = "/api/v1/students/me/notification-preferences"


class StubService:
    def __init__(self) -> None:
        self.records = [
            NotificationPreferenceRecord(
                type_code="UPCOMING_CLASS",
                description="Upcoming class",
                in_app_enabled=True,
                push_enabled=False,
                is_customized=False,
            )
        ]
        self.updates = None

    async def list_for_user(self, pool, user_id):
        return self.records

    async def update_for_user(self, pool, *, user_id, updates):
        self.updates = updates
        return [
            NotificationPreferenceRecord(
                type_code=updates[0].type_code,
                description="Upcoming class",
                in_app_enabled=updates[0].in_app_enabled,
                push_enabled=updates[0].push_enabled,
                is_customized=True,
            )
        ]


def client(jwks_document, service: StubService) -> TestClient:
    app = create_app(enable_database=False)
    app.state.db_pool = FakePool(default_connection())
    app.state.settings = build_settings()
    app.dependency_overrides[get_authentication_service] = lambda: (
        build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_notification_preferences_service] = lambda: service
    return TestClient(app)


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_preferences_require_authentication(jwks_document) -> None:
    response = client(jwks_document, StubService()).get(URL)
    assert response.status_code == 401


def test_get_returns_effective_default_values(jwks_document, make_access_token) -> None:
    response = client(jwks_document, StubService()).get(
        URL,
        headers=auth(make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))),
    )
    assert response.status_code == 200
    assert response.json() == [
        {
            "typeCode": "UPCOMING_CLASS",
            "description": "Upcoming class",
            "inAppEnabled": True,
            "pushEnabled": False,
            "isCustomized": False,
        }
    ]


def test_put_updates_and_returns_effective_values(jwks_document, make_access_token) -> None:
    service = StubService()
    response = client(jwks_document, service).put(
        URL,
        headers=auth(make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))),
        json={
            "preferences": [
                {
                    "typeCode": "UPCOMING_CLASS",
                    "inAppEnabled": False,
                    "pushEnabled": True,
                }
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()[0]["isCustomized"] is True
    assert service.updates[0].push_enabled is True


@pytest.mark.asyncio
async def test_repository_effective_query_falls_back_to_type_defaults() -> None:
    from modules.notification.preferences.repository import NotificationPreferencesRepository

    connection = AsyncMock()
    connection.fetch.return_value = [
        {
            "code": "UPCOMING_CLASS",
            "description": "Upcoming class",
            "is_customized": False,
        }
    ]
    user_id = uuid4()
    producer_repository = AsyncMock()
    producer_repository.fetch_user_preferences.return_value = {user_id: (True, False)}

    records = await NotificationPreferencesRepository(producer_repository).list_effective(
        connection,
        user_id,
    )

    assert records[0].is_customized is False
    assert records[0].in_app_enabled is True
    assert records[0].push_enabled is False
    producer_repository.fetch_user_preferences.assert_awaited_once_with(
        connection,
        [user_id],
        "UPCOMING_CLASS",
    )
    query = connection.fetch.call_args.args[0]
    assert "user_configurable IS TRUE" in query
