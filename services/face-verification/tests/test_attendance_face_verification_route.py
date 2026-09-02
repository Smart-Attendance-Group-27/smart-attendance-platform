from unittest.mock import AsyncMock
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies.attendance import (
    get_attendance_face_verification_service,
)
from api.dependencies.auth import get_current_student_id
from api.routes.attendance import router
from services.attendance_face_verification_service import (
    AttendanceFaceVerificationResult,
    AttendanceFaceVerificationService,
    AttendanceFaceVerificationStatus,
)


SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
STUDENT_ID = UUID("23000000-0000-0000-0000-000000000001")


def build_client(result: AttendanceFaceVerificationResult) -> tuple[TestClient, AsyncMock]:
    app = FastAPI()
    app.include_router(router)
    service = AsyncMock(spec=AttendanceFaceVerificationService)
    service.verify.return_value = result
    app.dependency_overrides[get_current_student_id] = lambda: STUDENT_ID
    app.dependency_overrides[get_attendance_face_verification_service] = (
        lambda: service
    )
    return TestClient(app), service


def test_returns_attempt_metadata_for_a_retryable_failure() -> None:
    client, service = build_client(
        AttendanceFaceVerificationResult(
            status=AttendanceFaceVerificationStatus.NO_FACE,
            attempt_number=2,
            can_retry=True,
        )
    )

    with client:
        response = client.post(
            f"/internal/v1/attendance-sessions/{SESSION_ID}/face-verifications",
            files={"image": ("capture.jpg", b"jpeg", "image/jpeg")},
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "no_face",
        "attemptNumber": 2,
        "canRetry": True,
    }
    service.verify.assert_awaited_once_with(
        session_id=SESSION_ID,
        student_id=STUDENT_ID,
        captured_image=b"jpeg",
    )

