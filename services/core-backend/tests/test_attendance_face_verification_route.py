from datetime import datetime
from uuid import UUID

from fastapi.testclient import TestClient

from conftest import (
    FakePool,
    STUDENT_USER_ID,
    build_authentication_service_for_tests,
    build_settings,
    default_connection,
)
from main import create_app
from modules.attendance_verification.check_in.domain import (
    CheckInOutcome,
    CheckInResult,
    InitialCheckIn,
)
from modules.attendance_verification.check_in.exception import (
    VerificationNotStartedError,
)
from modules.attendance_verification.check_in.route import get_check_in_service
from modules.attendance_verification.attendance_state import InitialCheckInStatus
from modules.attendance_verification.face.client import (
    FaceVerificationServiceError,
    FaceVerificationServiceInvalidRequestError,
    FaceVerificationServiceRejectedError,
    InternalFaceVerificationResult,
)
from modules.attendance_verification.face.route import (
    get_face_verification_service_client,
    get_face_progress_repository,
)
from modules.identity.auth.dependencies import get_authentication_service


SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
ATTEMPT_ID = UUID("50000000-0000-0000-0000-000000000001")
URL = f"/api/v1/attendance-sessions/{SESSION_ID}/face-verifications"


class StubFaceVerificationClient:
    def __init__(
        self,
        result: InternalFaceVerificationResult | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[dict[str, object]] = []

    async def verify_attendance_face(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


class StubFaceProgressRepository:
    def __init__(self, passed: bool) -> None:
        self.passed = passed
        self.calls: list[dict[str, object]] = []

    async def has_passed(self, _pool, **kwargs):
        self.calls.append(kwargs)
        return self.passed


class StubCheckInService:
    """No pass here checks anyone in unless the test asks for it."""

    def __init__(self, result: CheckInResult | None = None) -> None:
        self.result = result or CheckInResult(
            outcome=CheckInOutcome.PENDING,
            verification_attempt_id=ATTEMPT_ID,
        )
        self.calls: list[tuple[UUID, UUID]] = []

    async def check_in_for_user(self, pool, user_id, session_id):
        self.calls.append((user_id, session_id))
        return self.result


def build_client(
    jwks_document,
    service: StubFaceVerificationClient,
    check_in_service: StubCheckInService | None = None,
) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_face_verification_service_client] = (
        lambda: service
    )
    app.dependency_overrides[get_check_in_service] = (
        lambda: check_in_service or StubCheckInService()
    )
    return TestClient(app, raise_server_exceptions=False)


def test_reports_that_face_verification_already_passed(
    jwks_document,
    make_access_token,
) -> None:
    service = StubFaceVerificationClient(
        InternalFaceVerificationResult(
            status="failed",
            attempt_number=1,
            can_retry=True,
        )
    )
    repository = StubFaceProgressRepository(passed=True)
    app_client = build_client(jwks_document, service)
    app_client.app.dependency_overrides[get_face_progress_repository] = (
        lambda: repository
    )

    with app_client as client:
        response = client.get(
            URL,
            headers={"Authorization": f"Bearer {make_access_token()}"},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "passed"}
    assert repository.calls == [
        {
            "user_id": STUDENT_USER_ID,
            "session_id": SESSION_ID,
        }
    ]


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
        "initialCheckIn": None,
    }
    assert service.calls == [
        {
            "session_id": SESSION_ID,
            "access_token": token,
            "image": b"jpeg",
            "content_type": "image/jpeg",
            "liveness": None,
        }
    ]


def test_forwards_the_liveness_field_when_the_client_sends_one(
    jwks_document,
    make_access_token,
) -> None:
    service = StubFaceVerificationClient(
        InternalFaceVerificationResult(
            status="passed",
            attempt_number=1,
            can_retry=False,
        )
    )

    with build_client(jwks_document, service) as client:
        client.post(
            URL,
            headers={"Authorization": f"Bearer {make_access_token()}"},
            files={"image": ("capture.jpg", b"jpeg", "image/jpeg")},
            data={"liveness": "blink-token-123"},
        )

    assert service.calls[0]["liveness"] == "blink-token-123"


def test_a_pass_checks_the_student_in_and_reports_it(
    jwks_document,
    make_access_token,
) -> None:
    service = StubFaceVerificationClient(
        InternalFaceVerificationResult(
            status="passed",
            attempt_number=1,
            can_retry=False,
        )
    )
    check_in_service = StubCheckInService(
        CheckInResult(
            outcome=CheckInOutcome.CHECKED_IN,
            verification_attempt_id=ATTEMPT_ID,
            initial_check_in=InitialCheckIn(
                checked_in_at=datetime.fromisoformat("2026-09-21T09:03:00+00:00"),
                status=InitialCheckInStatus.CHECKED_IN,
            ),
            was_persisted=True,
        )
    )

    with build_client(jwks_document, service, check_in_service) as client:
        response = client.post(
            URL,
            headers={"Authorization": f"Bearer {make_access_token()}"},
            files={"image": ("capture.jpg", b"jpeg", "image/jpeg")},
        )

    body = response.json()
    assert body["initialCheckIn"]["status"] == "checked_in"
    assert len(check_in_service.calls) == 1


def test_a_failure_to_check_in_after_a_pass_does_not_fail_the_request(
    jwks_document,
    make_access_token,
) -> None:
    class RaisingCheckInService:
        async def check_in_for_user(self, pool, user_id, session_id):
            raise VerificationNotStartedError("no attempt yet")

    service = StubFaceVerificationClient(
        InternalFaceVerificationResult(
            status="passed",
            attempt_number=1,
            can_retry=False,
        )
    )

    with build_client(jwks_document, service, RaisingCheckInService()) as client:
        response = client.post(
            URL,
            headers={"Authorization": f"Bearer {make_access_token()}"},
            files={"image": ("capture.jpg", b"jpeg", "image/jpeg")},
        )

    assert response.status_code == 200
    assert response.json()["initialCheckIn"] is None


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
        "initialCheckIn": None,
    }


def test_rejects_an_unsupported_image_type(
    jwks_document,
    make_access_token,
) -> None:
    service = StubFaceVerificationClient()

    with build_client(jwks_document, service) as client:
        response = client.post(
            URL,
            headers={"Authorization": f"Bearer {make_access_token()}"},
            files={"image": ("capture.gif", b"gif-bytes", "image/gif")},
        )

    assert response.status_code == 415
    assert response.json()["detail"] == {
        "code": "UNSUPPORTED_IMAGE_TYPE",
        "message": "Only JPEG and PNG images are supported",
    }
    assert service.calls == []


def test_rejects_an_empty_image(jwks_document, make_access_token) -> None:
    service = StubFaceVerificationClient()

    with build_client(jwks_document, service) as client:
        response = client.post(
            URL,
            headers={"Authorization": f"Bearer {make_access_token()}"},
            files={"image": ("capture.jpg", b"", "image/jpeg")},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == {
        "code": "EMPTY_IMAGE",
        "message": "The uploaded image is empty",
    }
    assert service.calls == []


def test_maps_a_rejected_capture_to_a_conflict(
    jwks_document,
    make_access_token,
) -> None:
    service = StubFaceVerificationClient(
        error=FaceVerificationServiceRejectedError("No matching reference face."),
    )

    with build_client(jwks_document, service) as client:
        response = client.post(
            URL,
            headers={"Authorization": f"Bearer {make_access_token()}"},
            files={"image": ("capture.jpg", b"jpeg", "image/jpeg")},
        )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "FACE_VERIFICATION_REJECTED",
        "message": "No matching reference face.",
    }


def test_maps_an_invalid_capture_to_unprocessable(
    jwks_document,
    make_access_token,
) -> None:
    service = StubFaceVerificationClient(
        error=FaceVerificationServiceInvalidRequestError("Malformed capture."),
    )

    with build_client(jwks_document, service) as client:
        response = client.post(
            URL,
            headers={"Authorization": f"Bearer {make_access_token()}"},
            files={"image": ("capture.jpg", b"jpeg", "image/jpeg")},
        )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "FACE_VERIFICATION_INVALID_REQUEST",
        "message": "Malformed capture.",
    }


def test_maps_a_face_service_outage_to_unavailable(
    jwks_document,
    make_access_token,
) -> None:
    service = StubFaceVerificationClient(
        error=FaceVerificationServiceError("The face service did not respond."),
    )

    with build_client(jwks_document, service) as client:
        response = client.post(
            URL,
            headers={"Authorization": f"Bearer {make_access_token()}"},
            files={"image": ("capture.jpg", b"jpeg", "image/jpeg")},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "FACE_VERIFICATION_SERVICE_ERROR",
        "message": "The face service did not respond.",
    }
