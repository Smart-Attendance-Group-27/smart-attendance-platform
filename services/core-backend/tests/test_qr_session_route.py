import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient

from conftest import (
    LINKED_LECTURER_SUBJECT,
    LINKED_STUDENT_SUBJECT,
    FakePool,
    build_authentication_service_for_tests,
    build_settings,
    default_connection,
)
from main import create_app
from modules.attendance_sessions.qr_session.exception import (
    ActiveStudentProfileNotFoundError,
    AttendanceSessionNotActiveError,
    AttendanceSessionNotFoundError,
    DynamicQrConfigurationError,
    DynamicQrSessionUnavailableError,
    LecturerSessionAccessError,
    QrNotRequiredError,
    QrSessionNotFoundError,
    StudentNotEligibleError,
    VerificationNotStartedError,
)
from modules.attendance_sessions.qr_session.route import get_qr_session_service
from modules.attendance_sessions.qr_session.service import (
    CreatedQrSession,
    CurrentDynamicQrSession,
    VerifiedQrSession,
)
from modules.identity.auth.dependencies import get_authentication_service

SESSION_ID = "40000000-0000-0000-0000-000000000001"
QR_SESSION_ID = "50000000-0000-0000-0000-000000000001"


def authorize(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def lecturer_token(make_access_token) -> str:
    return make_access_token(subject=LINKED_LECTURER_SUBJECT, roles=("lecturer",))


def student_token(make_access_token) -> str:
    return make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))


class SuccessfulQrSessionService:
    async def create_static_qr_session(
        self,
        pool: object,
        attendance_session_id: UUID,
        valid_for_seconds: int,
        lecturer_id: UUID,
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
        lecturer_id: UUID,
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
        student_user_id: UUID,
    ) -> VerifiedQrSession:
        return VerifiedQrSession(
            qr_session_id=qr_session_id,
            status="accepted",
            verified_at=datetime(2026, 8, 6, 10, 3, tzinfo=UTC),
        )

    async def assert_lecturer_owns_qr_session(
        self,
        pool: object,
        qr_session_id: UUID,
        lecturer_id: UUID,
    ) -> None:
        return None

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


class MissingAttendanceSessionService(SuccessfulQrSessionService):
    async def create_static_qr_session(
        self,
        pool: object,
        attendance_session_id: UUID,
        valid_for_seconds: int,
        lecturer_id: UUID,
    ) -> CreatedQrSession:
        raise AttendanceSessionNotFoundError()


class InactiveAttendanceSessionService(SuccessfulQrSessionService):
    async def create_static_qr_session(
        self,
        pool: object,
        attendance_session_id: UUID,
        valid_for_seconds: int,
        lecturer_id: UUID,
    ) -> CreatedQrSession:
        raise AttendanceSessionNotActiveError("Attendance session is not active.")


class NotOwnedAttendanceSessionService(SuccessfulQrSessionService):
    async def create_static_qr_session(
        self,
        pool: object,
        attendance_session_id: UUID,
        valid_for_seconds: int,
        lecturer_id: UUID,
    ) -> CreatedQrSession:
        raise LecturerSessionAccessError()


class QrNotRequiredService(SuccessfulQrSessionService):
    async def create_static_qr_session(
        self,
        pool: object,
        attendance_session_id: UUID,
        valid_for_seconds: int,
        lecturer_id: UUID,
    ) -> CreatedQrSession:
        raise QrNotRequiredError()


class MissingQrSessionService(SuccessfulQrSessionService):
    async def assert_lecturer_owns_qr_session(
        self,
        pool: object,
        qr_session_id: UUID,
        lecturer_id: UUID,
    ) -> None:
        raise QrSessionNotFoundError()


class NotOwnedQrSessionService(SuccessfulQrSessionService):
    async def assert_lecturer_owns_qr_session(
        self,
        pool: object,
        qr_session_id: UUID,
        lecturer_id: UUID,
    ) -> None:
        raise LecturerSessionAccessError()


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
        student_user_id: UUID,
    ) -> VerifiedQrSession:
        raise DynamicQrConfigurationError(
            "Dynamic QR HMAC secret is not configured.",
        )


class InactiveStudentProfileVerifyService(SuccessfulQrSessionService):
    async def verify_qr_session(
        self,
        pool: object,
        qr_session_id: UUID,
        qr_value: str,
        student_user_id: UUID,
    ) -> VerifiedQrSession:
        raise ActiveStudentProfileNotFoundError()


class IneligibleStudentVerifyService(SuccessfulQrSessionService):
    async def verify_qr_session(
        self,
        pool: object,
        qr_session_id: UUID,
        qr_value: str,
        student_user_id: UUID,
    ) -> VerifiedQrSession:
        raise StudentNotEligibleError()


class VerificationNotStartedVerifyService(SuccessfulQrSessionService):
    async def verify_qr_session(
        self,
        pool: object,
        qr_session_id: UUID,
        qr_value: str,
        student_user_id: UUID,
    ) -> VerifiedQrSession:
        raise VerificationNotStartedError()


def build_client(jwks_document, service) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_qr_session_service] = lambda: service
    return TestClient(app)


def test_create_static_qr_session_route_returns_camel_case_response(
    jwks_document,
    make_access_token,
) -> None:
    with build_client(jwks_document, SuccessfulQrSessionService()) as client:
        response = client.post(
            f"/api/v1/attendance-sessions/{SESSION_ID}/qr-sessions",
            headers=authorize(lecturer_token(make_access_token)),
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


def test_create_qr_session_route_rejects_non_lecturer_role(
    jwks_document,
    make_access_token,
) -> None:
    with build_client(jwks_document, SuccessfulQrSessionService()) as client:
        response = client.post(
            f"/api/v1/attendance-sessions/{SESSION_ID}/qr-sessions",
            headers=authorize(student_token(make_access_token)),
            json={"validForSeconds": 300},
        )

    assert response.status_code == 403


def test_create_qr_session_route_requires_bearer_token(jwks_document) -> None:
    with build_client(jwks_document, SuccessfulQrSessionService()) as client:
        response = client.post(
            f"/api/v1/attendance-sessions/{SESSION_ID}/qr-sessions",
            json={"validForSeconds": 300},
        )

    assert response.status_code == 401


def test_create_static_qr_session_route_accepts_optional_body(
    jwks_document,
    make_access_token,
) -> None:
    with build_client(jwks_document, SuccessfulQrSessionService()) as client:
        response = client.post(
            f"/api/v1/attendance-sessions/{SESSION_ID}/qr-sessions",
            headers=authorize(lecturer_token(make_access_token)),
        )

    assert response.status_code == 201


def test_create_qr_session_route_accepts_dynamic_mode_contract(
    jwks_document,
    make_access_token,
) -> None:
    with build_client(jwks_document, SuccessfulQrSessionService()) as client:
        response = client.post(
            f"/api/v1/attendance-sessions/{SESSION_ID}/qr-sessions",
            headers=authorize(lecturer_token(make_access_token)),
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


def test_create_static_qr_session_route_rejects_invalid_validity(
    jwks_document,
    make_access_token,
) -> None:
    with build_client(jwks_document, SuccessfulQrSessionService()) as client:
        response = client.post(
            f"/api/v1/attendance-sessions/{SESSION_ID}/qr-sessions",
            headers=authorize(lecturer_token(make_access_token)),
            json={"validForSeconds": 10},
        )

    assert response.status_code == 422


def test_create_static_qr_session_route_maps_missing_session_to_404(
    jwks_document,
    make_access_token,
) -> None:
    with build_client(jwks_document, MissingAttendanceSessionService()) as client:
        response = client.post(
            f"/api/v1/attendance-sessions/{SESSION_ID}/qr-sessions",
            headers=authorize(lecturer_token(make_access_token)),
            json={"validForSeconds": 300},
        )

    assert response.status_code == 404


def test_create_static_qr_session_route_maps_not_owned_session_to_404(
    jwks_document,
    make_access_token,
) -> None:
    with build_client(jwks_document, NotOwnedAttendanceSessionService()) as client:
        response = client.post(
            f"/api/v1/attendance-sessions/{SESSION_ID}/qr-sessions",
            headers=authorize(lecturer_token(make_access_token)),
            json={"validForSeconds": 300},
        )

    assert response.status_code == 404


def test_create_static_qr_session_route_maps_qr_not_required_to_409(
    jwks_document,
    make_access_token,
) -> None:
    with build_client(jwks_document, QrNotRequiredService()) as client:
        response = client.post(
            f"/api/v1/attendance-sessions/{SESSION_ID}/qr-sessions",
            headers=authorize(lecturer_token(make_access_token)),
            json={"validForSeconds": 300},
        )

    assert response.status_code == 409


def test_create_static_qr_session_route_maps_inactive_session_to_409(
    jwks_document,
    make_access_token,
) -> None:
    with build_client(jwks_document, InactiveAttendanceSessionService()) as client:
        response = client.post(
            f"/api/v1/attendance-sessions/{SESSION_ID}/qr-sessions",
            headers=authorize(lecturer_token(make_access_token)),
            json={"validForSeconds": 300},
        )

    assert response.status_code == 409
    assert response.json() == {"detail": "Attendance session is not active."}


def test_verify_qr_session_route_returns_camel_case_response(
    jwks_document,
    make_access_token,
) -> None:
    with build_client(jwks_document, SuccessfulQrSessionService()) as client:
        response = client.post(
            f"/api/v1/qr-sessions/{QR_SESSION_ID}/verify",
            headers=authorize(student_token(make_access_token)),
            json={"qrValue": "raw-test-token"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "qrSessionId": "50000000-0000-0000-0000-000000000001",
        "status": "accepted",
        "verifiedAt": "2026-08-06T10:03:00Z",
    }


def test_verify_qr_session_route_rejects_non_student_role(
    jwks_document,
    make_access_token,
) -> None:
    with build_client(jwks_document, SuccessfulQrSessionService()) as client:
        response = client.post(
            f"/api/v1/qr-sessions/{QR_SESSION_ID}/verify",
            headers=authorize(lecturer_token(make_access_token)),
            json={"qrValue": "raw-test-token"},
        )

    assert response.status_code == 403


def test_verify_qr_session_route_requires_bearer_token(jwks_document) -> None:
    with build_client(jwks_document, SuccessfulQrSessionService()) as client:
        response = client.post(
            f"/api/v1/qr-sessions/{QR_SESSION_ID}/verify",
            json={"qrValue": "raw-test-token"},
        )

    assert response.status_code == 401


def test_verify_qr_session_route_rejects_malformed_uuid(
    jwks_document,
    make_access_token,
) -> None:
    with build_client(jwks_document, SuccessfulQrSessionService()) as client:
        response = client.post(
            "/api/v1/qr-sessions/not-a-uuid/verify",
            headers=authorize(student_token(make_access_token)),
            json={"qrValue": "raw-test-token"},
        )

    assert response.status_code == 422


def test_verify_qr_session_route_rejects_missing_qr_value(
    jwks_document,
    make_access_token,
) -> None:
    with build_client(jwks_document, SuccessfulQrSessionService()) as client:
        response = client.post(
            f"/api/v1/qr-sessions/{QR_SESSION_ID}/verify",
            headers=authorize(student_token(make_access_token)),
            json={},
        )

    assert response.status_code == 422


def test_verify_qr_session_route_maps_dynamic_config_error_to_500(
    jwks_document,
    make_access_token,
) -> None:
    with build_client(jwks_document, MissingDynamicQrSecretVerifyService()) as client:
        response = client.post(
            f"/api/v1/qr-sessions/{QR_SESSION_ID}/verify",
            headers=authorize(student_token(make_access_token)),
            json={"qrValue": "dynamic-qr-value"},
        )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Dynamic QR HMAC secret is not configured.",
    }


def test_verify_qr_session_route_maps_missing_student_profile_to_404(
    jwks_document,
    make_access_token,
) -> None:
    with build_client(jwks_document, InactiveStudentProfileVerifyService()) as client:
        response = client.post(
            f"/api/v1/qr-sessions/{QR_SESSION_ID}/verify",
            headers=authorize(student_token(make_access_token)),
            json={"qrValue": "raw-test-token"},
        )

    assert response.status_code == 404


def test_verify_qr_session_route_maps_ineligible_student_to_403(
    jwks_document,
    make_access_token,
) -> None:
    with build_client(jwks_document, IneligibleStudentVerifyService()) as client:
        response = client.post(
            f"/api/v1/qr-sessions/{QR_SESSION_ID}/verify",
            headers=authorize(student_token(make_access_token)),
            json={"qrValue": "raw-test-token"},
        )

    assert response.status_code == 403


def test_verify_qr_session_route_maps_verification_not_started_to_409(
    jwks_document,
    make_access_token,
) -> None:
    with build_client(jwks_document, VerificationNotStartedVerifyService()) as client:
        response = client.post(
            f"/api/v1/qr-sessions/{QR_SESSION_ID}/verify",
            headers=authorize(student_token(make_access_token)),
            json={"qrValue": "raw-test-token"},
        )

    assert response.status_code == 409


def test_get_current_dynamic_qr_session_route_returns_camel_case_response(
    jwks_document,
    make_access_token,
) -> None:
    with build_client(jwks_document, SuccessfulQrSessionService()) as client:
        response = client.get(
            f"/api/v1/qr-sessions/{QR_SESSION_ID}/current",
            headers=authorize(lecturer_token(make_access_token)),
        )

    assert response.status_code == 200
    assert response.json() == {
        "qrSessionId": "50000000-0000-0000-0000-000000000001",
        "qrValue": "current-dynamic-qr-value",
        "sequence": 17,
        "validFrom": "2026-08-06T10:04:15Z",
        "expiresAt": "2026-08-06T10:04:30Z",
    }


def test_get_current_dynamic_qr_session_route_rejects_non_lecturer_role(
    jwks_document,
    make_access_token,
) -> None:
    with build_client(jwks_document, SuccessfulQrSessionService()) as client:
        response = client.get(
            f"/api/v1/qr-sessions/{QR_SESSION_ID}/current",
            headers=authorize(student_token(make_access_token)),
        )

    assert response.status_code == 403


def test_get_current_dynamic_qr_session_route_maps_not_owned_to_404(
    jwks_document,
    make_access_token,
) -> None:
    with build_client(jwks_document, NotOwnedQrSessionService()) as client:
        response = client.get(
            f"/api/v1/qr-sessions/{QR_SESSION_ID}/current",
            headers=authorize(lecturer_token(make_access_token)),
        )

    assert response.status_code == 404


def test_get_current_dynamic_qr_session_route_maps_missing_session_to_404(
    jwks_document,
    make_access_token,
) -> None:
    with build_client(jwks_document, MissingQrSessionService()) as client:
        response = client.get(
            f"/api/v1/qr-sessions/{QR_SESSION_ID}/current",
            headers=authorize(lecturer_token(make_access_token)),
        )

    assert response.status_code == 404


def test_get_current_dynamic_qr_session_route_rejects_static_session(
    jwks_document,
    make_access_token,
) -> None:
    with build_client(jwks_document, StaticQrSessionCurrentService()) as client:
        response = client.get(
            f"/api/v1/qr-sessions/{QR_SESSION_ID}/current",
            headers=authorize(lecturer_token(make_access_token)),
        )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "QR session is not a dynamic QR session.",
    }


def test_get_current_dynamic_qr_session_route_rejects_missing_secret(
    jwks_document,
    make_access_token,
) -> None:
    with build_client(jwks_document, MissingDynamicQrSecretService()) as client:
        response = client.get(
            f"/api/v1/qr-sessions/{QR_SESSION_ID}/current",
            headers=authorize(lecturer_token(make_access_token)),
        )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Dynamic QR HMAC secret is not configured.",
    }


def test_stream_dynamic_qr_session_route_sends_named_rotation_event(
    jwks_document,
    make_access_token,
) -> None:
    with build_client(jwks_document, SuccessfulQrSessionService()) as client:
        with client.stream(
            "GET",
            f"/api/v1/qr-sessions/{QR_SESSION_ID}/stream",
            headers=authorize(lecturer_token(make_access_token)),
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


def test_stream_dynamic_qr_session_route_rejects_static_session_before_streaming(
    jwks_document,
    make_access_token,
) -> None:
    with build_client(jwks_document, StaticQrSessionCurrentService()) as client:
        response = client.get(
            f"/api/v1/qr-sessions/{QR_SESSION_ID}/stream",
            headers=authorize(lecturer_token(make_access_token)),
        )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "QR session is not a dynamic QR session.",
    }


def test_stream_dynamic_qr_session_route_requires_bearer_token(jwks_document) -> None:
    with build_client(jwks_document, SuccessfulQrSessionService()) as client:
        response = client.get(f"/api/v1/qr-sessions/{QR_SESSION_ID}/stream")

    assert response.status_code == 401
