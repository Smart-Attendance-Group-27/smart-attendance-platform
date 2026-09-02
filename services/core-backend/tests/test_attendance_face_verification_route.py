from uuid import UUID

from fastapi.testclient import TestClient

from conftest import (
    FakePool,
    build_authentication_service_for_tests,
    build_settings,
    default_connection,
)
from main import create_app
from modules.attendance_verification.face.client import (
    InternalFaceVerificationResult,
)
from modules.attendance_verification.face.route import (
    get_face_verification_service_client,
)
from modules.identity.auth.dependencies import get_authentication_service


SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
URL = f"/api/v1/attendance-sessions/{SESSION_ID}/face-verifications"


class StubFaceVerificationClient:
    def __init__(self, result: InternalFaceVerificationResult) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    async def verify_attendance_face(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


def build_client(jwks_document, service: StubFaceVerificationClient) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_face_verification_service_client] = (
        lambda: service
    )
    return TestClient(app, raise_server_exceptions=False)


def test_maps_internal_pass_and_forwards_authenticated_capture(
    jwks_document,
    make_access_token,
) -> None:
    service = StubFaceVerificationClient(
        InternalFaceVerificationResult(
            status="passed",
            attempt_number=2,
            can_retry=False,
        )
    )
    token = make_access_token()

    with build_client(jwks_document, service) as client:
        response = client.post(
            URL,
            headers={"Authorization": f"Bearer {token}"},
            files={"image": ("capture.jpg", b"jpeg", "image/jpeg")},
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "attemptNumber": 2,
        "canRetry": False,
    }
    assert service.calls == [
        {
            "session_id": SESSION_ID,
            "access_token": token,
            "image": b"jpeg",
            "content_type": "image/jpeg",
        }
    ]


def test_maps_last_internal_failure_as_non_retryable(
    jwks_document,
    make_access_token,
) -> None:
    service = StubFaceVerificationClient(
        InternalFaceVerificationResult(
            status="failed",
            attempt_number=3,
            can_retry=False,
        )
    )

    with build_client(jwks_document, service) as client:
        response = client.post(
            URL,
            headers={"Authorization": f"Bearer {make_access_token()}"},
            files={"image": ("capture.jpg", b"jpeg", "image/jpeg")},
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "verification_failure",
        "attemptNumber": 3,
        "canRetry": False,
    }

