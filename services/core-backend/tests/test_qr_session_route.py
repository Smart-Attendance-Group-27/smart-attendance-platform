from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient

from main import create_app
from modules.attendance_sessions.qr_session.exception import (
    AttendanceSessionNotActiveError,
    AttendanceSessionNotFoundError,
)
from modules.attendance_sessions.qr_session.route import get_qr_session_service
from modules.attendance_sessions.qr_session.service import CreatedQrSession


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
            qr_value="raw-test-token",
            status="active",
            valid_from=datetime(2026, 8, 6, 10, 0, tzinfo=UTC),
            expires_at=datetime(2026, 8, 6, 10, 5, tzinfo=UTC),
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
        "qrValue": "raw-test-token",
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
