import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from unittest.mock import patch
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse
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
    FaceVerificationServiceClient,
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
LIVENESS_JSON = (
    '{"version":1,"method":"mlkit_challenge","passed":true,'
    '"challenges":["turn_left","eyes_closed_hold"],'
    '"startedAt":"2026-09-22T08:00:00Z",'
    '"completedAt":"2026-09-22T08:00:10Z",'
    '"engine":"uniattend-mobile-liveness"}'
)
URL = f"/api/v1/attendance-sessions/{SESSION_ID}/face-verifications"
LIVENESS_NOW = datetime(2026, 9, 22, 8, 0, 30, tzinfo=UTC)


def load_face_liveness_module():
    module_name = "_integration_face_liveness_evidence"
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing

    module_path = (
        Path(__file__).resolve().parents[2]
        / "face-verification"
        / "services"
        / "liveness_evidence.py"
    )
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the face-service liveness validator")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def build_enforced_face_app(
    liveness,
    *,
    received_liveness: list[str | None],
    biometric_attempts: list[bytes],
    validated_evidence: list[object] | None = None,
) -> FastAPI:
    app = FastAPI()
    downstream_path = (
        "/internal/v1/attendance-sessions/{session_id}/face-verifications"
    )

    @app.post(downstream_path)
    async def enforced_face_verification(
        session_id: UUID,
        image: Annotated[UploadFile, File()],
        liveness_field: Annotated[str | None, Form(alias="liveness")] = None,
    ):
        del session_id
        received_liveness.append(liveness_field)
        try:
            evidence = liveness.validate_liveness_evidence(
                liveness_field,
            )
        except liveness.LivenessEvidenceValidationError:
            return JSONResponse(
                status_code=422,
                content={"status": "liveness_failure"},
            )

        if validated_evidence is not None:
            validated_evidence.append(evidence)
        biometric_attempts.append(await image.read())
        return {
            "status": "passed",
            "attemptNumber": 1,
            "canRetry": False,
        }

    return app


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
            data={"liveness": LIVENESS_JSON},
        )

    assert service.calls[0]["liveness"] == LIVENESS_JSON


def test_rejects_oversized_liveness_with_structured_error(
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
        response = client.post(
            URL,
            headers={"Authorization": f"Bearer {make_access_token()}"},
            files={"image": ("capture.jpg", b"jpeg", "image/jpeg")},
            data={"liveness": "x" * 4097},
        )

    assert response.status_code == 413
    assert response.json() == {
        "detail": {
            "code": "LIVENESS_EVIDENCE_TOO_LARGE",
            "message": "The liveness evidence is too large",
        }
    }
    assert service.calls == []


def test_missing_liveness_is_rejected_through_the_backend_chain(
    jwks_document,
    make_access_token,
) -> None:
    liveness = load_face_liveness_module()
    received_liveness: list[str | None] = []
    biometric_attempts: list[bytes] = []
    face_app = build_enforced_face_app(
        liveness,
        received_liveness=received_liveness,
        biometric_attempts=biometric_attempts,
    )

    service = FaceVerificationServiceClient(
        base_url="http://face-verification:8001",
        timeout_seconds=30,
    )
    check_in_service = StubCheckInService()
    downstream_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=face_app),
    )

    with patch(
        "modules.attendance_verification.face.client.httpx.AsyncClient",
        return_value=downstream_client,
    ):
        with build_client(
            jwks_document,
            service,
            check_in_service,
        ) as client:
            response = client.post(
                URL,
                headers={"Authorization": f"Bearer {make_access_token()}"},
                files={"image": ("capture.jpg", b"jpeg", "image/jpeg")},
            )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "FACE_VERIFICATION_INVALID_REQUEST",
        "message": "The capture or its liveness evidence was rejected.",
    }
    assert received_liveness == [None]
    assert biometric_attempts == []
    assert check_in_service.calls == []


@pytest.mark.parametrize(
    "serialized_liveness",
    [
        "{",
        LIVENESS_JSON.replace('"passed":true', '"passed":false'),
        LIVENESS_JSON.replace('"version":1', '"version":2'),
        LIVENESS_JSON.replace(
            '"startedAt":"2026-09-22T08:00:00Z",'
            '"completedAt":"2026-09-22T08:00:10Z"',
            '"startedAt":"2026-09-22T07:57:00Z",'
            '"completedAt":"2026-09-22T07:58:00Z"',
        ),
        LIVENESS_JSON.replace(
            '"startedAt":"2026-09-22T08:00:00Z",'
            '"completedAt":"2026-09-22T08:00:10Z"',
            '"startedAt":"2026-09-22T08:00:30Z",'
            '"completedAt":"2026-09-22T08:00:36Z"',
        ),
        LIVENESS_JSON.replace(
            '["turn_left","eyes_closed_hold"]',
            '["turn_left","turn_left"]',
        ),
        LIVENESS_JSON.replace("eyes_closed_hold", "smile"),
        LIVENESS_JSON + (" " * 2048),
    ],
    ids=[
        "malformed-json",
        "passed-false",
        "wrong-version",
        "expired",
        "future-invalid",
        "duplicate-challenges",
        "unsupported-challenge",
        "oversized-json",
    ],
)
def test_invalid_liveness_is_preserved_and_rejected_through_backend_chain(
    serialized_liveness: str,
    jwks_document,
    make_access_token,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    liveness = load_face_liveness_module()
    monkeypatch.setattr(liveness, "_utc_now", lambda: LIVENESS_NOW)
    received_liveness: list[str | None] = []
    biometric_attempts: list[bytes] = []
    face_app = build_enforced_face_app(
        liveness,
        received_liveness=received_liveness,
        biometric_attempts=biometric_attempts,
    )
    service = FaceVerificationServiceClient(
        base_url="http://face-verification:8001",
        timeout_seconds=30,
    )
    check_in_service = StubCheckInService()
    downstream_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=face_app),
    )

    with patch(
        "modules.attendance_verification.face.client.httpx.AsyncClient",
        return_value=downstream_client,
    ):
        with build_client(
            jwks_document,
            service,
            check_in_service,
        ) as client:
            response = client.post(
                URL,
                headers={"Authorization": f"Bearer {make_access_token()}"},
                files={"image": ("capture.jpg", b"jpeg", "image/jpeg")},
                data={"liveness": serialized_liveness},
            )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "FACE_VERIFICATION_INVALID_REQUEST",
        "message": "The capture or its liveness evidence was rejected.",
    }
    assert received_liveness == [serialized_liveness]
    assert biometric_attempts == []
    assert check_in_service.calls == []


def test_valid_liveness_allows_face_verification_through_backend_chain(
    jwks_document,
    make_access_token,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    liveness = load_face_liveness_module()
    monkeypatch.setattr(liveness, "_utc_now", lambda: LIVENESS_NOW)
    received_liveness: list[str | None] = []
    validated_evidence: list[object] = []
    biometric_attempts: list[bytes] = []
    face_app = build_enforced_face_app(
        liveness,
        received_liveness=received_liveness,
        biometric_attempts=biometric_attempts,
        validated_evidence=validated_evidence,
    )
    service = FaceVerificationServiceClient(
        base_url="http://face-verification:8001",
        timeout_seconds=30,
    )
    downstream_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=face_app),
    )

    with patch(
        "modules.attendance_verification.face.client.httpx.AsyncClient",
        return_value=downstream_client,
    ):
        with build_client(jwks_document, service) as client:
            response = client.post(
                URL,
                headers={"Authorization": f"Bearer {make_access_token()}"},
                files={"image": ("capture.jpg", b"jpeg", "image/jpeg")},
                data={"liveness": LIVENESS_JSON},
            )

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "attemptNumber": 1,
        "canRetry": False,
        "initialCheckIn": None,
    }
    assert received_liveness == [LIVENESS_JSON]
    assert len(validated_evidence) == 1
    evidence = validated_evidence[0]
    assert evidence.passed is True
    assert evidence.challenges == ("turn_left", "eyes_closed_hold")
    assert evidence.engine == "uniattend-mobile-liveness"
    assert biometric_attempts == [b"jpeg"]




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


@pytest.mark.parametrize("internal_status", ["processing_failed", "model_mismatch"])
def test_maps_operational_face_failure_as_retryable_verification_failure(
    internal_status,
    jwks_document,
    make_access_token,
) -> None:
    service = StubFaceVerificationClient(
        InternalFaceVerificationResult(
            status=internal_status,
            attempt_number=1,
            can_retry=True,
        )
    )

    with build_client(jwks_document, service) as client:
        response = client.post(
            URL,
            headers={"Authorization": f"Bearer {make_access_token()}"},
            files={"image": ("capture.jpg", b"jpeg", "image/jpeg")},
            data={"liveness": LIVENESS_JSON},
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "verification_failure",
        "attemptNumber": 1,
        "canRetry": True,
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
