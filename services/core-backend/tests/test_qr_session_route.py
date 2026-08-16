import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient

from main import create_app
from modules.attendance_sessions.qr_session.exception import (
    AttendanceSessionNotActiveError,
    AttendanceSessionNotFoundError,
    DynamicQrConfigurationError,
    DynamicQrSessionUnavailableError,
    QrSessionNotFoundError,
)
from modules.attendance_sessions.qr_session.route import get_qr_session_service
from modules.attendance_sessions.qr_session.service import (
    CreatedQrSession,
    CurrentDynamicQrSession,
    VerifiedQrSession,
)


class SuccessfulQrSessionService:
    async def create_static_qr_session(
        self,
        pool: object,
        attendance_session_id: UUID,
        valid_for_seconds: int,
    ) -> CreatedQrSession:
        return CreatedQrSession(
            qr_session_id=UUID("50000000-0000-0000-0000-000000000001"),
            attendance_session_id=attendance_session_id,
            mode="static",
            qr_value="raw-test-token",
            refresh_interval_seconds=None,
            status="active",
            valid_from=datetime(2026, 8, 6, 10, 0, tzinfo=UTC),
            expires_at=datetime(2026, 8, 6, 10, 5, tzinfo=UTC),
        )

    async def create_dynamic_qr_session(
        self,
        pool: object,
        attendance_session_id: UUID,
        valid_for_seconds: int,
        refresh_interval_seconds: int,
    ) -> CreatedQrSession:
        return CreatedQrSession(
            qr_session_id=UUID("50000000-0000-0000-0000-000000000002"),
            attendance_session_id=attendance_session_id,
            mode="dynamic",
            qr_value=None,
            refresh_interval_seconds=refresh_interval_seconds,
            status="active",
            valid_from=datetime(2026, 8, 6, 10, 0, tzinfo=UTC),
            expires_at=datetime(2026, 8, 6, 10, 15, tzinfo=UTC),
        )

    async def verify_qr_session(
        self,
        pool: object,
        qr_session_id: UUID,
        qr_value: str,
    ) -> VerifiedQrSession:
        return VerifiedQrSession(
            qr_session_id=qr_session_id,
            status="accepted",
            verified_at=datetime(2026, 8, 6, 10, 3, tzinfo=UTC),
        )

    async def get_current_dynamic_qr_session(
        self,
        pool: object,
        qr_session_id: UUID,
    ) -> CurrentDynamicQrSession:
        return CurrentDynamicQrSession(
            qr_session_id=qr_session_id,
            qr_value="current-dynamic-qr-value",
            sequence=17,
            valid_from=datetime(2026, 8, 6, 10, 4, 15, tzinfo=UTC),
            expires_at=datetime(2026, 8, 6, 10, 4, 30, tzinfo=UTC),
        )

    async def stream_current_dynamic_qr_sessions(
        self,
        pool: object,
        qr_session_id: UUID,
        *,
        initial_qr_session: CurrentDynamicQrSession | None = None,
        is_disconnected: object | None = None,
    ):
        yield initial_qr_session or await self.get_current_dynamic_qr_session(
            pool,
            qr_session_id,
        )


class MissingAttendanceSessionService:
    async def create_static_qr_session(
        self,
        pool: object,
        attendance_session_id: UUID,
        valid_for_seconds: int,
    ) -> CreatedQrSession:
        raise AttendanceSessionNotFoundError()


class InactiveAttendanceSessionService:
    async def create_static_qr_session(
        self,
        pool: object,
        attendance_session_id: UUID,
        valid_for_seconds: int,
    ) -> CreatedQrSession:
        raise AttendanceSessionNotActiveError("Attendance session is not active.")


class MissingQrSessionService(SuccessfulQrSessionService):
    async def get_current_dynamic_qr_session(
        self,
        pool: object,
        qr_session_id: UUID,
    ) -> CurrentDynamicQrSession:
        raise QrSessionNotFoundError()


class StaticQrSessionCurrentService(SuccessfulQrSessionService):
    async def get_current_dynamic_qr_session(
        self,
        pool: object,
        qr_session_id: UUID,
    ) -> CurrentDynamicQrSession:
        raise DynamicQrSessionUnavailableError(
            "QR session is not a dynamic QR session.",
        )


class MissingDynamicQrSecretService(SuccessfulQrSessionService):
    async def get_current_dynamic_qr_session(
        self,
        pool: object,
        qr_session_id: UUID,
    ) -> CurrentDynamicQrSession:
        raise DynamicQrConfigurationError(
            "Dynamic QR HMAC secret is not configured.",
        )


class MissingDynamicQrSecretVerifyService(SuccessfulQrSessionService):
    async def verify_qr_session(
        self,
        pool: object,
        qr_session_id: UUID,
        qr_value: str,
    ) -> VerifiedQrSession:
        raise DynamicQrConfigurationError(
            "Dynamic QR HMAC secret is not configured.",
        )


def test_create_static_qr_session_route_returns_camel_case_response() -> None:
    app = create_app(enable_database=False)
    app.state.db_pool = object()
    app.dependency_overrides[get_qr_session_service] = SuccessfulQrSessionService

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/attendance-sessions/40000000-0000-0000-0000-000000000001/qr-sessions",
            json={"validForSeconds": 300},
        )

    assert response.status_code == 201
    assert response.json() == {
        "qrSessionId": "50000000-0000-0000-0000-000000000001",
        "attendanceSessionId": "40000000-0000-0000-0000-000000000001",
        "mode": "static",
        "qrValue": "raw-test-token",
        "refreshIntervalSeconds": None,
        "status": "active",
        "validFrom": "2026-08-06T10:00:00Z",
        "expiresAt": "2026-08-06T10:05:00Z",
    }


def test_create_static_qr_session_route_accepts_optional_body() -> None:
    app = create_app(enable_database=False)
    app.state.db_pool = object()
    app.dependency_overrides[get_qr_session_service] = SuccessfulQrSessionService

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/attendance-sessions/40000000-0000-0000-0000-000000000001/qr-sessions",
        )

    assert response.status_code == 201


def test_create_qr_session_route_accepts_dynamic_mode_contract() -> None:
    app = create_app(enable_database=False)
    app.state.db_pool = object()
    app.dependency_overrides[get_qr_session_service] = SuccessfulQrSessionService

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/attendance-sessions/40000000-0000-0000-0000-000000000001/qr-sessions",
            json={
                "mode": "dynamic",
                "validForSeconds": 900,
                "refreshIntervalSeconds": 15,
            },
        )

    assert response.status_code == 201
    assert response.json() == {
        "qrSessionId": "50000000-0000-0000-0000-000000000002",
        "attendanceSessionId": "40000000-0000-0000-0000-000000000001",
        "mode": "dynamic",
        "qrValue": None,
        "refreshIntervalSeconds": 15,
        "status": "active",
        "validFrom": "2026-08-06T10:00:00Z",
        "expiresAt": "2026-08-06T10:15:00Z",
    }


def test_create_static_qr_session_route_rejects_invalid_validity() -> None:
    app = create_app(enable_database=False)
    app.state.db_pool = object()
    app.dependency_overrides[get_qr_session_service] = SuccessfulQrSessionService

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/attendance-sessions/40000000-0000-0000-0000-000000000001/qr-sessions",
            json={"validForSeconds": 10},
        )

    assert response.status_code == 422


def test_create_static_qr_session_route_maps_missing_session_to_404() -> None:
    app = create_app(enable_database=False)
    app.state.db_pool = object()
    app.dependency_overrides[get_qr_session_service] = MissingAttendanceSessionService

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/attendance-sessions/40000000-0000-0000-0000-000000000001/qr-sessions",
            json={"validForSeconds": 300},
        )

    assert response.status_code == 404


def test_create_static_qr_session_route_maps_inactive_session_to_409() -> None:
    app = create_app(enable_database=False)
    app.state.db_pool = object()
    app.dependency_overrides[get_qr_session_service] = InactiveAttendanceSessionService

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/attendance-sessions/40000000-0000-0000-0000-000000000001/qr-sessions",
            json={"validForSeconds": 300},
        )

    assert response.status_code == 409
    assert response.json() == {"detail": "Attendance session is not active."}


def test_verify_qr_session_route_returns_camel_case_response() -> None:
    app = create_app(enable_database=False)
    app.state.db_pool = object()
    app.dependency_overrides[get_qr_session_service] = SuccessfulQrSessionService

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/qr-sessions/50000000-0000-0000-0000-000000000001/verify",
            json={"qrValue": "raw-test-token"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "qrSessionId": "50000000-0000-0000-0000-000000000001",
        "status": "accepted",
        "verifiedAt": "2026-08-06T10:03:00Z",
    }


def test_verify_qr_session_route_rejects_malformed_uuid() -> None:
    app = create_app(enable_database=False)
    app.state.db_pool = object()
    app.dependency_overrides[get_qr_session_service] = SuccessfulQrSessionService

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/qr-sessions/not-a-uuid/verify",
            json={"qrValue": "raw-test-token"},
        )

    assert response.status_code == 422


def test_verify_qr_session_route_rejects_missing_qr_value() -> None:
    app = create_app(enable_database=False)
    app.state.db_pool = object()
    app.dependency_overrides[get_qr_session_service] = SuccessfulQrSessionService

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/qr-sessions/50000000-0000-0000-0000-000000000001/verify",
            json={},
        )

    assert response.status_code == 422


def test_verify_qr_session_route_maps_dynamic_config_error_to_500() -> None:
    app = create_app(enable_database=False)
    app.state.db_pool = object()
    app.dependency_overrides[get_qr_session_service] = (
        MissingDynamicQrSecretVerifyService
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/qr-sessions/50000000-0000-0000-0000-000000000001/verify",
            json={"qrValue": "dynamic-qr-value"},
        )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Dynamic QR HMAC secret is not configured.",
    }


def test_get_current_dynamic_qr_session_route_returns_camel_case_response() -> None:
    app = create_app(enable_database=False)
    app.state.db_pool = object()
    app.dependency_overrides[get_qr_session_service] = SuccessfulQrSessionService

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/qr-sessions/50000000-0000-0000-0000-000000000001/current",
        )

    assert response.status_code == 200
    assert response.json() == {
        "qrSessionId": "50000000-0000-0000-0000-000000000001",
        "qrValue": "current-dynamic-qr-value",
        "sequence": 17,
        "validFrom": "2026-08-06T10:04:15Z",
        "expiresAt": "2026-08-06T10:04:30Z",
    }


def test_get_current_dynamic_qr_session_route_maps_missing_session_to_404() -> None:
    app = create_app(enable_database=False)
    app.state.db_pool = object()
    app.dependency_overrides[get_qr_session_service] = MissingQrSessionService

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/qr-sessions/50000000-0000-0000-0000-000000000001/current",
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "QR session was not found."}


def test_get_current_dynamic_qr_session_route_rejects_static_session() -> None:
    app = create_app(enable_database=False)
    app.state.db_pool = object()
    app.dependency_overrides[get_qr_session_service] = StaticQrSessionCurrentService

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/qr-sessions/50000000-0000-0000-0000-000000000001/current",
        )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "QR session is not a dynamic QR session.",
    }


def test_get_current_dynamic_qr_session_route_rejects_missing_secret() -> None:
    app = create_app(enable_database=False)
    app.state.db_pool = object()
    app.dependency_overrides[get_qr_session_service] = MissingDynamicQrSecretService

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/qr-sessions/50000000-0000-0000-0000-000000000001/current",
        )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Dynamic QR HMAC secret is not configured.",
    }


def test_stream_dynamic_qr_session_route_sends_named_rotation_event() -> None:
    app = create_app(enable_database=False)
    app.state.db_pool = object()
    app.dependency_overrides[get_qr_session_service] = SuccessfulQrSessionService

    with TestClient(app) as client:
        with client.stream(
            "GET",
            "/api/v1/qr-sessions/50000000-0000-0000-0000-000000000001/stream",
        ) as response:
            body = next(response.iter_text())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: qr.rotate" in body
    assert "retry: 3000" in body
    payload_line = next(line for line in body.splitlines() if line.startswith("data: "))
    assert json.loads(payload_line.removeprefix("data: ")) == {
        "qrSessionId": "50000000-0000-0000-0000-000000000001",
        "qrValue": "current-dynamic-qr-value",
        "sequence": 17,
        "validFrom": "2026-08-06T10:04:15Z",
        "expiresAt": "2026-08-06T10:04:30Z",
    }


def test_stream_dynamic_qr_session_route_rejects_static_session_before_streaming() -> None:
    app = create_app(enable_database=False)
    app.state.db_pool = object()
    app.dependency_overrides[get_qr_session_service] = StaticQrSessionCurrentService

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/qr-sessions/50000000-0000-0000-0000-000000000001/stream",
        )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "QR session is not a dynamic QR session.",
    }
