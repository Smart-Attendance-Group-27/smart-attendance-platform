from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies.attendance import get_attendance_face_verification_service
from api.dependencies.auth import get_current_student_id
from api.routes.attendance import MAX_IMAGE_BYTES, router
from services.attendance_face_verification_service import (
    AttendanceFaceVerificationResult,
    AttendanceFaceVerificationService,
    AttendanceFaceVerificationStatus,
)


def create_test_app(
    *,
    student_id: UUID | None = None,
    service: AsyncMock | None = None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    if student_id is not None:
        app.dependency_overrides[get_current_student_id] = lambda: student_id

    if service is not None:
        app.dependency_overrides[get_attendance_face_verification_service] = lambda: service

    return app


def create_service(
    *,
    student_id: UUID,
    result_status: AttendanceFaceVerificationStatus,
    similarity_score: float | None = None,
) -> AsyncMock:
    service = AsyncMock(spec=AttendanceFaceVerificationService)
    service.verify.return_value = AttendanceFaceVerificationResult(
        status=result_status,
        student_id=student_id,
        similarity_score=similarity_score,
    )
    return service


def post_image(
    client: TestClient,
    session_id: UUID,
    *,
    content: bytes = b"encoded-jpeg-image",
    content_type: str = "image/jpeg",
):
    return client.post(
        f"/api/v1/face-verification/attendance-sessions/{session_id}/verify",
        files={"image": ("capture.jpg", content, content_type)},
    )


def test_valid_jpeg_returns_passed_result() -> None:
    student_id = uuid4()
    session_id = uuid4()
    captured_image = b"encoded-jpeg-image"
    service = create_service(
        student_id=student_id,
        result_status=AttendanceFaceVerificationStatus.PASSED,
        similarity_score=0.93,
    )
    app = create_test_app(student_id=student_id, service=service)

    with TestClient(app) as client:
        response = post_image(client, session_id, content=captured_image)

    assert response.status_code == 200
    assert response.json() == {
        "status": "passed",
        "message": "Face verification passed",
        "similarityScore": 0.93,
    }
    service.verify.assert_awaited_once_with(
        session_id=session_id,
        student_id=student_id,
        captured_image=captured_image,
    )


def test_rejects_unsupported_image_type() -> None:
    student_id = uuid4()
    session_id = uuid4()
    service = create_service(student_id=student_id, result_status=AttendanceFaceVerificationStatus.PASSED)
    app = create_test_app(student_id=student_id, service=service)

    with TestClient(app) as client:
        response = post_image(client, session_id, content=b"not-an-image", content_type="text/plain")

    assert response.status_code == 415
    service.verify.assert_not_awaited()


def test_rejects_empty_image() -> None:
    student_id = uuid4()
    session_id = uuid4()
    service = create_service(student_id=student_id, result_status=AttendanceFaceVerificationStatus.PASSED)
    app = create_test_app(student_id=student_id, service=service)

    with TestClient(app) as client:
        response = post_image(client, session_id, content=b"")

    assert response.status_code == 400
    service.verify.assert_not_awaited()


def test_rejects_image_larger_than_limit() -> None:
    student_id = uuid4()
    session_id = uuid4()
    service = create_service(student_id=student_id, result_status=AttendanceFaceVerificationStatus.PASSED)
    app = create_test_app(student_id=student_id, service=service)

    with TestClient(app) as client:
        response = post_image(client, session_id, content=b"x" * (MAX_IMAGE_BYTES + 1))

    assert response.status_code == 413
    service.verify.assert_not_awaited()


def test_rejects_unauthenticated_request() -> None:
    student_id = uuid4()
    session_id = uuid4()
    service = create_service(student_id=student_id, result_status=AttendanceFaceVerificationStatus.PASSED)
    app = create_test_app(service=service)

    with TestClient(app) as client:
        response = post_image(client, session_id)

    assert response.status_code == 401
    service.verify.assert_not_awaited()


def test_returns_unavailable_when_service_dependency_is_not_ready() -> None:
    student_id = uuid4()
    session_id = uuid4()
    app = create_test_app(student_id=student_id)

    with TestClient(app) as client:
        response = post_image(client, session_id)

    assert response.status_code == 503


@pytest.mark.parametrize(
    ("result_status", "expected_message"),
    [
        (AttendanceFaceVerificationStatus.FAILED, "Face verification failed"),
        (
            AttendanceFaceVerificationStatus.VERIFICATION_ATTEMPT_NOT_FOUND,
            "No verification attempt was found for this session — complete the geofence check first",
        ),
        (
            AttendanceFaceVerificationStatus.VERIFICATION_ATTEMPT_CLOSED,
            "This session's verification attempt is already complete",
        ),
        (AttendanceFaceVerificationStatus.PROFILE_NOT_ENROLLED, "A reference face profile is not available"),
        (AttendanceFaceVerificationStatus.NO_ACTIVE_CONFIG, "Face verification is unavailable"),
        (AttendanceFaceVerificationStatus.NO_FACE, "No face was detected"),
        (AttendanceFaceVerificationStatus.MULTIPLE_FACES, "More than one face was detected"),
        (AttendanceFaceVerificationStatus.LOW_QUALITY, "The captured image quality is too low"),
        (AttendanceFaceVerificationStatus.PROCESSING_FAILED, "The captured image could not be processed"),
        (AttendanceFaceVerificationStatus.MODEL_MISMATCH, "Face verification is unavailable"),
    ],
)
def test_returns_safe_message_for_non_success_result(
    result_status: AttendanceFaceVerificationStatus,
    expected_message: str,
) -> None:
    student_id = uuid4()
    session_id = uuid4()
    service = create_service(student_id=student_id, result_status=result_status)
    app = create_test_app(student_id=student_id, service=service)

    with TestClient(app) as client:
        response = post_image(client, session_id)

    assert response.status_code == 200
    assert response.json() == {
        "status": result_status.value,
        "message": expected_message,
        "similarityScore": None,
    }
