from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies.auth import get_current_student_id
from api.dependencies.readiness import get_readiness_verification_service
from api.routes.readiness import MAX_IMAGE_BYTES, router
from services.readiness_verification_service import (
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


def post_image(client: TestClient,*,content: bytes = b"encoded-jpeg-image",content_type: str = "image/jpeg",):
    return client.post("/api/v1/face-verification/readiness",
        files={"image": ("capture.jpg",content,content_type,)},
    )


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
