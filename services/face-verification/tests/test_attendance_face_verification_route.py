import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
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
from repositories.attendance_face_verification_repository import (
    AttendanceVerificationContext,
)
from repositories.face_profile_repository import StoredFaceEmbedding
from services import liveness_evidence as liveness_evidence_module
from services.attendance_face_verification_service import (
    AttendanceFaceVerificationResult,
    AttendanceFaceVerificationService,
    AttendanceFaceVerificationStatus,
)
from services.face_comparison_service import (
    FaceComparisonResult,
    FaceComparisonStatus,
)


SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
STUDENT_ID = UUID("23000000-0000-0000-0000-000000000001")
ATTEMPT_ID = UUID("50000000-0000-0000-0000-000000000001")
PROFILE_ID = UUID("60000000-0000-0000-0000-000000000001")
CONFIG_ID = UUID("70000000-0000-0000-0000-000000000001")
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


def build_attempt_integration_client(
    comparison_status: FaceComparisonStatus,
    *,
    existing_attempt_number: int | None = None,
) -> tuple[TestClient, AsyncMock, AsyncMock]:
    session = AsyncMock()
    repository = AsyncMock()
    repository.lock_verification_context.return_value = (
        AttendanceVerificationContext(
            verification_attempt_id=ATTEMPT_ID,
            verification_status="in_progress",
            session_status="active",
            requires_face_verification=True,
            requires_geofence=False,
            latest_geofence_status=None,
            check_in_opens_at=NOW - timedelta(minutes=5),
            check_in_closes_at=NOW + timedelta(minutes=20),
            closed_at=None,
            cancelled_at=None,
        )
    )
    repository.lock_latest_face_attempt.return_value = (
        None
        if existing_attempt_number is None
        else SimpleNamespace(
            attempt_number=existing_attempt_number,
            validation_status="failed",
        )
    )
    profiles = AsyncMock()
    profiles.get_stored_embedding_for_comparison.return_value = (
        StoredFaceEmbedding(
            profile_id=PROFILE_ID,
            student_id=STUDENT_ID,
            embedding=(1.0, 0.0),
            model_name="buffalo_l",
            model_version="1",
            dimension=2,
        )
    )
    configs = AsyncMock()
    configs.get_active.return_value = SimpleNamespace(
        id=CONFIG_ID,
        similarity_threshold=Decimal("0.5"),
    )
    comparison_service = AsyncMock()
    comparison_service.compare.return_value = FaceComparisonResult(
        status=comparison_status,
        similarity_score=(
            0.82 if comparison_status is FaceComparisonStatus.MATCHED else 0.31
        ),
        similarity_threshold=0.5,
        failure_reason=(
            None
            if comparison_status is FaceComparisonStatus.MATCHED
            else comparison_status.value
        ),
    )
    service = AttendanceFaceVerificationService(
        session=session,
        face_comparison_service=comparison_service,
        max_attempts=3,
        repository=repository,
        face_profile_repository=profiles,
        verification_config_repository=configs,
        clock=lambda: NOW,
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_student_id] = lambda: STUDENT_ID
    app.dependency_overrides[get_attendance_face_verification_service] = (
        lambda: service
    )
    app.dependency_overrides[get_face_verification_settings] = lambda: (
        SimpleNamespace(
            liveness_enforcement_enabled=True,
            liveness_max_age_seconds=120,
        )
    )
    return TestClient(app), repository, session


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


@pytest.mark.parametrize("enforcement_enabled", [False, True])
def test_accepts_valid_liveness_evidence(
    enforcement_enabled: bool,
) -> None:
    client, service = build_client(
        AttendanceFaceVerificationResult(
            status=AttendanceFaceVerificationStatus.PASSED,
            attempt_number=1,
            can_retry=False,
        ),
        enforcement_enabled=enforcement_enabled,
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


@pytest.mark.parametrize(
    "comparison_status",
    [
        FaceComparisonStatus.NO_FACE,
        FaceComparisonStatus.MULTIPLE_FACES,
        FaceComparisonStatus.LOW_QUALITY,
        FaceComparisonStatus.NOT_MATCHED,
        FaceComparisonStatus.MATCHED,
    ],
)
def test_valid_liveness_attempt_consuming_outcomes_persist_one_attempt(
    comparison_status: FaceComparisonStatus,
) -> None:
    client, repository, _ = build_attempt_integration_client(
        comparison_status
    )

    with client:
        response = client.post(
            f"/internal/v1/attendance-sessions/{SESSION_ID}/face-verifications",
            files={"image": ("capture.jpg", b"jpeg", "image/jpeg")},
            data={"liveness": liveness_evidence()},
        )

    assert response.status_code == 200
    saved = repository.save_latest_face_attempt.await_args.kwargs
    assert saved["attempt_number"] == 1
    assert saved["liveness_passed"] is True


@pytest.mark.parametrize(
    "comparison_status",
    [
        FaceComparisonStatus.PROCESSING_FAILED,
        FaceComparisonStatus.MODEL_MISMATCH,
    ],
)
def test_valid_liveness_operational_failures_do_not_consume_an_attempt(
    comparison_status: FaceComparisonStatus,
) -> None:
    client, repository, session = build_attempt_integration_client(
        comparison_status,
        existing_attempt_number=1,
    )

    with client:
        response = client.post(
            f"/internal/v1/attendance-sessions/{SESSION_ID}/face-verifications",
            files={"image": ("capture.jpg", b"jpeg", "image/jpeg")},
            data={"liveness": liveness_evidence()},
        )

    assert response.status_code == 200
    assert response.json()["attemptNumber"] == 1
    repository.save_latest_face_attempt.assert_not_awaited()
    repository.mark_verification_attempt_failed.assert_not_awaited()
    session.commit.assert_not_awaited()
