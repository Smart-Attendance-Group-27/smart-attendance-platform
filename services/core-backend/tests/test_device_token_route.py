"""Route-level tests for POST /api/v1/notifications/devices."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from conftest import (
    LINKED_STUDENT_SUBJECT,
    LINKED_LECTURER_SUBJECT,
    FakePool,
    build_authentication_service_for_tests,
    build_settings,
    default_connection,
)
from main import create_app
from modules.identity.auth.dependencies import get_authentication_service
from modules.notification.device_tokens.exception import (
    InvalidExpoPushTokenError,
    UnsupportedPlatformError,
)
from modules.notification.device_tokens.repository import DeviceTokenRecord
from modules.notification.device_tokens.route import get_device_token_service
from modules.notification.device_tokens.service import DeviceTokenService

TOKEN_ID = UUID("d0000000-0000-0000-0000-000000000001")
USER_ID = UUID("20000000-0000-0000-0000-000000000011")
REGISTERED_AT = datetime(2026, 8, 20, 0, 0, 0, tzinfo=UTC)

VALID_TOKEN = "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]"

DEVICES_URL = "/api/v1/notifications/devices"


def authorize(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def make_record(is_active: bool = True) -> DeviceTokenRecord:
    return DeviceTokenRecord(
        id=TOKEN_ID,
        user_id=USER_ID,
        expo_push_token=VALID_TOKEN,
        platform="android",
        is_active=is_active,
        registered_at=REGISTERED_AT,
        last_used_at=None,
        revoked_at=None,
    )


class StubDeviceTokenService:
    def __init__(self, *, record: DeviceTokenRecord | None = None, raises=None):
        self._record = record or make_record()
        self._raises = raises

    async def register(self, pool, *, user_id, expo_push_token, platform):
        if self._raises is not None:
            raise self._raises
        return self._record

    async def revoke(self, pool, *, user_id, expo_push_token):
        if self._raises is not None:
            raise self._raises
        return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_client(jwks_document, stub_service: StubDeviceTokenService):
    app = create_app(enable_database=False)
    pool = FakePool(default_connection())
    app.state.db_pool = pool
    app.state.settings = build_settings()

    auth_service = build_authentication_service_for_tests(jwks_document)
    app.dependency_overrides[get_authentication_service] = lambda: auth_service
    app.dependency_overrides[get_device_token_service] = lambda: stub_service
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Authentication guard
# ---------------------------------------------------------------------------


def test_register_device_requires_auth(jwks_document):
    client = make_client(jwks_document, StubDeviceTokenService())
    response = client.post(
        DEVICES_URL, json={"expoPushToken": VALID_TOKEN, "platform": "android"}
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Happy path — student
# ---------------------------------------------------------------------------


def test_register_device_student_returns_201(jwks_document, make_access_token):
    client = make_client(jwks_document, StubDeviceTokenService())
    token = make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))

    response = client.post(
        DEVICES_URL,
        json={"expoPushToken": VALID_TOKEN, "platform": "android"},
        headers=authorize(token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == str(TOKEN_ID)
    assert body["platform"] == "android"
    assert body["isActive"] is True


# ---------------------------------------------------------------------------
# Happy path — lecturer can also register
# ---------------------------------------------------------------------------


def test_register_device_lecturer_returns_201(jwks_document, make_access_token):
    client = make_client(jwks_document, StubDeviceTokenService())
    token = make_access_token(subject=LINKED_LECTURER_SUBJECT, roles=("lecturer",))

    response = client.post(
        DEVICES_URL,
        json={"expoPushToken": VALID_TOKEN, "platform": "android"},
        headers=authorize(token),
    )
    assert response.status_code == 201


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


def test_register_device_invalid_token_returns_422(jwks_document, make_access_token):
    stub = StubDeviceTokenService(raises=InvalidExpoPushTokenError("bad token"))
    client = make_client(jwks_document, stub)
    token = make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))

    response = client.post(
        DEVICES_URL,
        json={"expoPushToken": "not-a-token", "platform": "android"},
        headers=authorize(token),
    )
    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "INVALID_EXPO_PUSH_TOKEN",
        "message": "bad token",
    }


def test_register_device_unsupported_platform_returns_422(jwks_document, make_access_token):
    stub = StubDeviceTokenService(raises=UnsupportedPlatformError("bad platform"))
    client = make_client(jwks_document, stub)
    token = make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))

    response = client.post(
        DEVICES_URL,
        json={"expoPushToken": VALID_TOKEN, "platform": "windows"},
        headers=authorize(token),
    )
    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "UNSUPPORTED_PLATFORM",
        "message": "bad platform",
    }


# ---------------------------------------------------------------------------
# Revocation endpoints
# ---------------------------------------------------------------------------


def test_revoke_device_requires_auth(jwks_document):
    client = make_client(jwks_document, StubDeviceTokenService())
    response = client.post(
        f"{DEVICES_URL}/revoke", json={"expoPushToken": VALID_TOKEN}
    )
    assert response.status_code == 401


def test_revoke_device_post_returns_200(jwks_document, make_access_token):
    client = make_client(jwks_document, StubDeviceTokenService())
    token = make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))

    response = client.post(
        f"{DEVICES_URL}/revoke",
        json={"expoPushToken": VALID_TOKEN},
        headers=authorize(token),
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True, "revoked": True}


def test_revoke_device_delete_returns_200(jwks_document, make_access_token):
    client = make_client(jwks_document, StubDeviceTokenService())
    token = make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))

    response = client.request(
        "DELETE",
        DEVICES_URL,
        json={"expoPushToken": VALID_TOKEN},
        headers=authorize(token),
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True, "revoked": True}


def test_revoke_device_invalid_token_returns_422(jwks_document, make_access_token):
    stub = StubDeviceTokenService(raises=InvalidExpoPushTokenError("bad token"))
    client = make_client(jwks_document, stub)
    token = make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))

    response = client.post(
        f"{DEVICES_URL}/revoke",
        json={"expoPushToken": "bad-token"},
        headers=authorize(token),
    )
    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "INVALID_EXPO_PUSH_TOKEN",
        "message": "bad token",
    }
