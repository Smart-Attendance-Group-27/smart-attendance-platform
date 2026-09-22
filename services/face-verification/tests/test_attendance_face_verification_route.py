import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies.attendance import (
    get_attendance_face_verification_service,
)
from api.dependencies.auth import get_current_student_id
from api.dependencies.runtime import get_face_verification_settings
from api.routes.attendance import router
from services import liveness_evidence as liveness_evidence_module
from services.attendance_face_verification_service import (
    AttendanceFaceVerificationResult,
    AttendanceFaceVerificationService,
    AttendanceFaceVerificationStatus,
)


SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
STUDENT_ID = UUID("23000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 9, 22, 8, 0, 30, tzinfo=UTC)


@pytest.fixture(autouse=True)
def freeze_liveness_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(liveness_evidence_module, "_utc_now", lambda: NOW)


def liveness_evidence(**overrides: object) -> str:
    payload: dict[str, object] = {
        "version": 1,
        "method": "mlkit_challenge",
        "passed": True,
        "challenges": ["turn_left", "eyes_closed_hold"],
        "startedAt": "2026-09-22T08:00:00Z",
        "completedAt": "2026-09-22T08:00:10Z",
        "engine": "uniattend-mobile-liveness",
    }
    payload.update(overrides)
    return json.dumps(payload, separators=(",", ":"))


def build_client(
    result: AttendanceFaceVerificationResult,
    *,
    enforcement_enabled: bool = False,
) -> tuple[TestClient, AsyncMock]:
    app = FastAPI()
    app.include_router(router)
    service = AsyncMock(spec=AttendanceFaceVerificationService)
    service.verify.return_value = result
    app.dependency_overrides[get_current_student_id] = lambda: STUDENT_ID
    app.dependency_overrides[get_attendance_face_verification_service] = (
        lambda: service
    )
    app.dependency_overrides[get_face_verification_settings] = lambda: (
        SimpleNamespace(
            liveness_enforcement_enabled=enforcement_enabled,
            liveness_max_age_seconds=120,
        )
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
        liveness_evidence=None,
    )


def test_accepts_valid_liveness_evidence() -> None:
    client, service = build_client(
        AttendanceFaceVerificationResult(
            status=AttendanceFaceVerificationStatus.PASSED,
            attempt_number=1,
            can_retry=False,
        ),
        enforcement_enabled=True,
    )

    with client:
        response = client.post(
            f"/internal/v1/attendance-sessions/{SESSION_ID}/face-verifications",
            files={"image": ("capture.jpg", b"jpeg", "image/jpeg")},
            data={"liveness": liveness_evidence()},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "passed"
    verified_evidence = service.verify.await_args.kwargs["liveness_evidence"]
    assert verified_evidence is not None
    assert verified_evidence.passed is True


def test_liveness_rejection_does_not_start_attempt_consumption() -> None:
    client, service = build_client(
        AttendanceFaceVerificationResult(
            status=AttendanceFaceVerificationStatus.PASSED,
            attempt_number=1,
            can_retry=False,
        ),
        enforcement_enabled=True,
    )

    with client:
        response = client.post(
            f"/internal/v1/attendance-sessions/{SESSION_ID}/face-verifications",
            files={"image": ("capture.jpg", b"jpeg", "image/jpeg")},
        )

    assert response.status_code == 422
    assert response.json() == {"status": "liveness_failure"}
    service.verify.assert_not_awaited()


@pytest.mark.parametrize(
    "serialized_evidence",
    [
        "{",
        liveness_evidence(version=2),
        liveness_evidence(method="other"),
        liveness_evidence(passed=False),
        liveness_evidence(
            startedAt="2026-09-22T07:57:59Z",
            completedAt="2026-09-22T07:58:09Z",
        ),
        liveness_evidence(
            startedAt="2026-09-22T08:00:31Z",
            completedAt="2026-09-22T08:00:36Z",
        ),
        liveness_evidence(challenges=["turn_left", "turn_left"]),
        liveness_evidence(challenges=["turn_left", "smile"]),
    ],
    ids=[
        "malformed-json",
        "wrong-version",
        "wrong-method",
        "passed-false",
        "expired",
        "future-invalid",
        "duplicate-challenges",
        "unsupported-challenge",
    ],
)
def test_rejects_invalid_supplied_liveness_before_face_verification(
    serialized_evidence: str,
) -> None:
    client, service = build_client(
        AttendanceFaceVerificationResult(
            status=AttendanceFaceVerificationStatus.PASSED,
            attempt_number=1,
            can_retry=False,
        )
    )

    with client:
        response = client.post(
            f"/internal/v1/attendance-sessions/{SESSION_ID}/face-verifications",
            files={"image": ("capture.jpg", b"jpeg", "image/jpeg")},
            data={"liveness": serialized_evidence},
        )

    assert response.status_code == 422
    assert response.json() == {"status": "liveness_failure"}
    service.verify.assert_not_awaited()
