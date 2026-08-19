import logging
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies.auth import get_current_student_id
from api.dependencies.readiness import get_readiness_verification_service
from api.routes.readiness import MAX_IMAGE_BYTES, router
from services.readiness_verification_service import (
    ReadinessProfileStatus,
    ReadinessStatusResult,
    ReadinessVerificationResult,
    ReadinessVerificationService,
    ReadinessVerificationStatus,
)


def create_test_app(*,student_id: UUID | None = None,service: AsyncMock | None = None,) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    if student_id is not None:
        app.dependency_overrides[get_current_student_id] = lambda: student_id

    if service is not None:
        app.dependency_overrides[get_readiness_verification_service] = lambda: service

    return app


def create_service(*,student_id: UUID,result_status: ReadinessVerificationStatus,) -> AsyncMock:
    service = AsyncMock(spec=ReadinessVerificationService)
    service.verify.return_value = ReadinessVerificationResult(status=result_status,student_id=student_id,)

    return service


def create_status_service(
    *,
    result: ReadinessStatusResult,
) -> AsyncMock:
    service = AsyncMock(spec=ReadinessVerificationService)
    service.get_status.return_value = result
    return service


def post_image(client: TestClient,*,content: bytes = b"encoded-jpeg-image",content_type: str = "image/jpeg",):
    return client.post("/api/v1/face-verification/readiness",
        files={"image": ("capture.jpg",content,content_type,)},
    )


def get_status(client: TestClient):
    return client.get("/api/v1/face-verification/readiness/status")


def test_gets_authenticated_students_unchecked_readiness_status() -> None:
    student_id = uuid4()
    service = create_status_service(
        result=ReadinessStatusResult(
            status=ReadinessProfileStatus.NOT_CHECKED,
            requires_readiness_check=True,
        )
    )
    app = create_test_app(student_id=student_id, service=service)

    with TestClient(app) as client:
        response = get_status(client)

    assert response.status_code == 200
    assert response.json() == {
        "status": "not_checked",
        "requiresReadinessCheck": True,
        "checkedAt": None,
    }
    service.get_status.assert_awaited_once_with(student_id=student_id)


def test_gets_completed_readiness_status() -> None:
    student_id = uuid4()
    checked_at = datetime(2026, 8, 18, 10, 30, tzinfo=timezone.utc)
    service = create_status_service(
        result=ReadinessStatusResult(
            status=ReadinessProfileStatus.PASSED,
            requires_readiness_check=False,
            checked_at=checked_at,
        )
    )
    app = create_test_app(student_id=student_id, service=service)

    with TestClient(app) as client:
        response = get_status(client)

    assert response.status_code == 200
    assert response.json() == {
        "status": "passed",
        "requiresReadinessCheck": False,
        "checkedAt": "2026-08-18T10:30:00Z",
    }


def test_get_status_requires_authentication() -> None:
    service = create_status_service(
        result=ReadinessStatusResult(
            status=ReadinessProfileStatus.NOT_CHECKED,
            requires_readiness_check=True,
        )
    )
    app = create_test_app(service=service)

    with TestClient(app) as client:
        response = get_status(client)

    assert response.status_code == 401
    assert response.json() == {
        "detail": "A bearer access token is required."
    }
    assert response.headers["www-authenticate"] == "Bearer"
    service.get_status.assert_not_awaited()


def test_valid_jpeg_returns_passed_readiness_result() -> None:
    student_id = uuid4()
    captured_image = b"encoded-jpeg-image"
    service = create_service(student_id=student_id,result_status=ReadinessVerificationStatus.PASSED,)
    app = create_test_app(student_id=student_id, service=service)

    with TestClient(app) as client:
        response = post_image(client, content=captured_image)

    assert response.status_code == 200
    assert response.json() == {"status": "passed","message": "Face readiness verification passed",}

    service.verify.assert_awaited_once_with(student_id=student_id,captured_image=captured_image,)


def test_logs_comparison_diagnostics_in_development(
    caplog: pytest.LogCaptureFixture,
) -> None:
    student_id = uuid4()
    profile_id = uuid4()
    config_id = uuid4()
    service = AsyncMock(spec=ReadinessVerificationService)
    service.verify.return_value = ReadinessVerificationResult(
        status=ReadinessVerificationStatus.FAILED,
        student_id=student_id,
        profile_id=profile_id,
        verification_config_id=config_id,
        similarity_score=0.42,
        similarity_threshold=0.5,
        detection_confidence=0.91,
        model_name="buffalo_l",
        failure_reason="Face similarity was below the required threshold",
    )
    app = create_test_app(student_id=student_id, service=service)
    app.state.settings = SimpleNamespace(app_environment="development")

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        with TestClient(app) as client:
            response = post_image(client)

    assert response.status_code == 200
    assert "Face readiness diagnostic" in caplog.text
    assert "status=failed" in caplog.text
    assert "similarity_score=0.42" in caplog.text
    assert "similarity_threshold=0.5" in caplog.text
    assert "detection_confidence=0.91" in caplog.text
    assert "model_name=buffalo_l" in caplog.text


def test_does_not_log_comparison_diagnostics_in_production(
    caplog: pytest.LogCaptureFixture,
) -> None:
    student_id = uuid4()
    service = create_service(
        student_id=student_id,
        result_status=ReadinessVerificationStatus.FAILED,
    )
    app = create_test_app(student_id=student_id, service=service)
    app.state.settings = SimpleNamespace(app_environment="production")

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        with TestClient(app) as client:
            response = post_image(client)

    assert response.status_code == 200
    assert "Face readiness diagnostic" not in caplog.text


def test_rejects_unsupported_image_type() -> None:
    student_id = uuid4()
    service = create_service(student_id=student_id,result_status=ReadinessVerificationStatus.PASSED,)
    app = create_test_app(student_id=student_id, service=service)

    with TestClient(app) as client:
        response = post_image(client,content=b"not-an-image",content_type="text/plain",)

    assert response.status_code == 415
    assert response.json() == {"detail": "Only JPEG and PNG images are supported"}

    service.verify.assert_not_awaited()


def test_rejects_empty_image() -> None:
    student_id = uuid4()
    service = create_service(student_id=student_id,result_status=ReadinessVerificationStatus.PASSED,)
    app = create_test_app(student_id=student_id, service=service)

    with TestClient(app) as client:
        response = post_image(client, content=b"")

    assert response.status_code == 400
    assert response.json() == {"detail": "The uploaded image is empty"}

    service.verify.assert_not_awaited()


def test_rejects_image_larger_than_limit() -> None:
    student_id = uuid4()
    service = create_service(student_id=student_id,result_status=ReadinessVerificationStatus.PASSED,)
    app = create_test_app(student_id=student_id, service=service)

    with TestClient(app) as client:
        response = post_image(client,content=b"x" * (MAX_IMAGE_BYTES + 1),)

    assert response.status_code == 413
    assert response.json() == {"detail": "The uploaded image is too large"}

    service.verify.assert_not_awaited()


def test_requires_an_image_upload() -> None:
    student_id = uuid4()
    service = create_service(student_id=student_id,result_status=ReadinessVerificationStatus.PASSED,)
    app = create_test_app(student_id=student_id, service=service)

    with TestClient(app) as client:
        response = client.post("/api/v1/face-verification/readiness")

    assert response.status_code == 422
    service.verify.assert_not_awaited()


def test_rejects_unauthenticated_request() -> None:
    student_id = uuid4()
    service = create_service(student_id=student_id,result_status=ReadinessVerificationStatus.PASSED,)
    app = create_test_app(service=service)

    with TestClient(app) as client:
        response = post_image(client)

    assert response.status_code == 401
    assert response.json() == {"detail": "A bearer access token is required."}
    assert response.headers["www-authenticate"] == "Bearer"

    service.verify.assert_not_awaited()


def test_returns_unavailable_when_service_dependency_is_not_ready() -> None:
    student_id = uuid4()
    app = create_test_app(student_id=student_id)

    with TestClient(app) as client:
        response = post_image(client)
    
    assert response.status_code == 503
    assert response.json() == {"detail": "Face verification is unavailable"}


@pytest.mark.parametrize(
    ("result_status", "expected_message"),
    [
        (ReadinessVerificationStatus.FAILED,"Face readiness verification failed"),
        (ReadinessVerificationStatus.PROFILE_NOT_ENROLLED,"A reference face profile is not available"),
        (ReadinessVerificationStatus.NO_ACTIVE_CONFIG,"Face readiness verification is unavailable"),
        (ReadinessVerificationStatus.NO_FACE,"No face was detected"),
        (ReadinessVerificationStatus.MULTIPLE_FACES,"More than one face was detected"),
        (ReadinessVerificationStatus.LOW_QUALITY,"The captured image quality is too low"),
        (ReadinessVerificationStatus.PROCESSING_FAILED,"The captured image could not be processed"),
        (ReadinessVerificationStatus.MODEL_MISMATCH,"Face readiness verification is unavailable"),
    ],
)

def test_returns_safe_message_for_non_success_result(result_status: ReadinessVerificationStatus,expected_message: str,) -> None:
    
    student_id = uuid4()
    service = create_service(student_id=student_id,result_status=result_status,)
    app = create_test_app(student_id=student_id, service=service)

    with TestClient(app) as client:
        response = post_image(client)

    assert response.status_code == 200
    assert response.json() == {"status": result_status.value,"message": expected_message,}
    assert set(response.json()) == {"status", "message"}
