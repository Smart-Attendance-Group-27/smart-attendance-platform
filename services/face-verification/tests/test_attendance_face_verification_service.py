import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from repositories.attendance_face_verification_repository import (
    AttendanceVerificationContext,
)
from repositories.face_profile_repository import StoredFaceEmbedding
from services.attendance_face_verification_service import (
    AttendanceFaceVerificationService,
    AttendanceFaceVerificationStatus,
    VerificationClosedError,
)
from services.face_comparison_service import (
    FaceComparisonResult,
    FaceComparisonStatus,
)
from services.liveness_evidence import LivenessEvidence


SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
STUDENT_ID = UUID("23000000-0000-0000-0000-000000000001")
VERIFICATION_ATTEMPT_ID = UUID("50000000-0000-0000-0000-000000000001")
PROFILE_ID = UUID("60000000-0000-0000-0000-000000000001")
CONFIG_ID = UUID("70000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 8, 28, 8, 30, tzinfo=UTC)
VALID_LIVENESS_EVIDENCE = LivenessEvidence(
    version=1,
    method="mlkit_challenge",
    passed=True,
    challenges=("turn_left", "eyes_closed_hold"),
    started_at=NOW - timedelta(seconds=10),
    completed_at=NOW,
    engine="uniattend-mobile-liveness",
)


def build_context() -> AttendanceVerificationContext:
    return AttendanceVerificationContext(
        verification_attempt_id=VERIFICATION_ATTEMPT_ID,
        verification_status="in_progress",
        session_status="active",
        requires_face_verification=True,
        requires_geofence=True,
        latest_geofence_status="passed",
        check_in_opens_at=NOW - timedelta(minutes=5),
        check_in_closes_at=NOW + timedelta(minutes=20),
        closed_at=None,
        cancelled_at=None,
    )


def build_reference() -> StoredFaceEmbedding:
    return StoredFaceEmbedding(
        profile_id=PROFILE_ID,
        student_id=STUDENT_ID,
        embedding=(1.0, 0.0),
        model_name="buffalo_l",
        model_version="1",
        dimension=2,
    )


def build_service(
    *,
    comparison: FaceComparisonResult,
    existing: object | None = None,
):
    session = AsyncMock()
    repository = AsyncMock()
    repository.lock_verification_context.return_value = build_context()
    repository.lock_latest_face_attempt.return_value = existing
    face_profiles = AsyncMock()
    face_profiles.get_stored_embedding_for_comparison.return_value = (
        build_reference()
    )
    configs = AsyncMock()
    configs.get_active.return_value = SimpleNamespace(
        id=CONFIG_ID,
        similarity_threshold=Decimal("0.5"),
    )
    comparison_service = AsyncMock()
    comparison_service.compare.return_value = comparison
    service = AttendanceFaceVerificationService(
        session=session,
        face_comparison_service=comparison_service,
        max_attempts=3,
        repository=repository,
        face_profile_repository=face_profiles,
        verification_config_repository=configs,
        clock=lambda: NOW,
    )
    return service, session, repository, comparison_service


def test_matched_consumes_first_attempt_and_keeps_parent_open_for_qr() -> None:
    service, session, repository, _ = build_service(
        comparison=FaceComparisonResult(
            status=FaceComparisonStatus.MATCHED,
            similarity_score=0.82,
            similarity_threshold=0.5,
        )
    )

    result = asyncio.run(
        service.verify(
            session_id=SESSION_ID,
            student_id=STUDENT_ID,
            captured_image=b"capture",
            liveness_evidence=VALID_LIVENESS_EVIDENCE,
        )
    )

    assert result.status is AttendanceFaceVerificationStatus.PASSED
    assert result.attempt_number == 1
    assert result.can_retry is False
    saved = repository.save_latest_face_attempt.await_args.kwargs
    assert saved["existing"] is None
    assert saved["attempt_number"] == 1
    assert saved["liveness_passed"] is True
    assert saved["validation_status"] == "passed"
    repository.mark_verification_attempt_failed.assert_not_awaited()
    session.commit.assert_awaited_once()


def test_no_face_consumes_retry_and_updates_existing_record() -> None:
    existing = SimpleNamespace(
        attempt_number=1,
        validation_status="failed",
    )
    service, _, repository, _ = build_service(
        existing=existing,
        comparison=FaceComparisonResult(
            status=FaceComparisonStatus.NO_FACE,
            failure_reason="No face was detected",
        ),
    )

    result = asyncio.run(
        service.verify(
            session_id=SESSION_ID,
            student_id=STUDENT_ID,
            captured_image=b"capture",
            liveness_evidence=VALID_LIVENESS_EVIDENCE,
        )
    )

    assert result.status is AttendanceFaceVerificationStatus.NO_FACE
    assert result.attempt_number == 2
    assert result.can_retry is True
    saved = repository.save_latest_face_attempt.await_args.kwargs
    assert saved["existing"] is existing
    assert saved["attempt_number"] == 2
    repository.mark_verification_attempt_failed.assert_not_awaited()


def test_matched_retry_consumes_attempt_and_replaces_previous_failure() -> None:
    existing = SimpleNamespace(
        attempt_number=1,
        validation_status="failed",
    )
    service, _, repository, _ = build_service(
        existing=existing,
        comparison=FaceComparisonResult(
            status=FaceComparisonStatus.MATCHED,
            similarity_score=0.79,
            similarity_threshold=0.5,
        ),
    )

    result = asyncio.run(
        service.verify(
            session_id=SESSION_ID,
            student_id=STUDENT_ID,
            captured_image=b"capture",
            liveness_evidence=VALID_LIVENESS_EVIDENCE,
        )
    )

    assert result.status is AttendanceFaceVerificationStatus.PASSED
    assert result.attempt_number == 2
    saved = repository.save_latest_face_attempt.await_args.kwargs
    assert saved["existing"] is existing
    assert saved["attempt_number"] == 2
    assert saved["validation_status"] == "passed"
    assert saved["failure_reason"] is None
    repository.mark_verification_attempt_failed.assert_not_awaited()


def test_not_matched_consumes_final_attempt_and_closes_parent() -> None:
    existing = SimpleNamespace(
        attempt_number=2,
        validation_status="failed",
    )
    service, _, repository, _ = build_service(
        existing=existing,
        comparison=FaceComparisonResult(
            status=FaceComparisonStatus.NOT_MATCHED,
            similarity_score=0.31,
            similarity_threshold=0.5,
            failure_reason="Face similarity was below the required threshold",
        ),
    )

    result = asyncio.run(
        service.verify(
            session_id=SESSION_ID,
            student_id=STUDENT_ID,
            captured_image=b"capture",
            liveness_evidence=VALID_LIVENESS_EVIDENCE,
        )
    )

    assert result.status is AttendanceFaceVerificationStatus.FAILED
    assert result.attempt_number == 3
    assert result.can_retry is False
    saved = repository.save_latest_face_attempt.await_args.kwargs
    assert saved["existing"] is existing
    assert saved["attempt_number"] == 3
    repository.mark_verification_attempt_failed.assert_awaited_once_with(
        VERIFICATION_ATTEMPT_ID,
        failure_reason="FACE_ATTEMPT_LIMIT_REACHED",
        completed_at=NOW,
    )


@pytest.mark.parametrize(
    "comparison_status",
    [
        FaceComparisonStatus.MULTIPLE_FACES,
        FaceComparisonStatus.LOW_QUALITY,
    ],
)
def test_face_validation_failures_consume_one_attempt(
    comparison_status: FaceComparisonStatus,
) -> None:
    existing = SimpleNamespace(
        attempt_number=1,
        validation_status="failed",
    )
    service, session, repository, _ = build_service(
        existing=existing,
        comparison=FaceComparisonResult(
            status=comparison_status,
            failure_reason="Face validation failed",
        ),
    )

    result = asyncio.run(
        service.verify(
            session_id=SESSION_ID,
            student_id=STUDENT_ID,
            captured_image=b"capture",
            liveness_evidence=VALID_LIVENESS_EVIDENCE,
        )
    )

    assert result.attempt_number == 2
    assert result.can_retry is True
    saved = repository.save_latest_face_attempt.await_args.kwargs
    assert saved["existing"] is existing
    assert saved["attempt_number"] == 2
    repository.mark_verification_attempt_failed.assert_not_awaited()
    session.commit.assert_awaited_once()


@pytest.mark.parametrize(
    "comparison_status",
    [
        FaceComparisonStatus.PROCESSING_FAILED,
        FaceComparisonStatus.MODEL_MISMATCH,
    ],
)
def test_operational_failures_do_not_consume_an_attempt(
    comparison_status: FaceComparisonStatus,
) -> None:
    existing = SimpleNamespace(
        attempt_number=1,
        validation_status="failed",
    )
    service, session, repository, _ = build_service(
        existing=existing,
        comparison=FaceComparisonResult(
            status=comparison_status,
            failure_reason="Verification unavailable",
        ),
    )

    result = asyncio.run(
        service.verify(
            session_id=SESSION_ID,
            student_id=STUDENT_ID,
            captured_image=b"capture",
            liveness_evidence=VALID_LIVENESS_EVIDENCE,
        )
    )

    assert result.status is AttendanceFaceVerificationStatus(
        comparison_status.value
    )
    assert result.attempt_number == 1
    assert result.can_retry is True
    repository.save_latest_face_attempt.assert_not_awaited()
    repository.mark_verification_attempt_failed.assert_not_awaited()
    session.commit.assert_not_awaited()


def test_legacy_missing_liveness_allows_a_biometric_match() -> None:
    service, session, repository, _ = build_service(
        comparison=FaceComparisonResult(
            status=FaceComparisonStatus.MATCHED,
            similarity_score=0.82,
            similarity_threshold=0.5,
        )
    )

    result = asyncio.run(
        service.verify(
            session_id=SESSION_ID,
            student_id=STUDENT_ID,
            captured_image=b"capture",
            liveness_evidence=None,
        )
    )

    assert result.status is AttendanceFaceVerificationStatus.PASSED
    assert result.attempt_number == 1
    assert result.can_retry is False
    saved = repository.save_latest_face_attempt.await_args.kwargs
    assert saved["liveness_passed"] is None
    assert saved["validation_status"] == "passed"
    assert saved["failure_reason"] is None
    repository.mark_verification_attempt_failed.assert_not_awaited()
    session.commit.assert_awaited_once()


def test_legacy_missing_liveness_preserves_a_biometric_mismatch() -> None:
    service, session, repository, _ = build_service(
        comparison=FaceComparisonResult(
            status=FaceComparisonStatus.NOT_MATCHED,
            similarity_score=0.31,
            similarity_threshold=0.5,
            failure_reason="Face similarity was below the required threshold",
        )
    )

    result = asyncio.run(
        service.verify(
            session_id=SESSION_ID,
            student_id=STUDENT_ID,
            captured_image=b"capture",
            liveness_evidence=None,
        )
    )

    assert result.status is AttendanceFaceVerificationStatus.FAILED
    assert result.attempt_number == 1
    assert result.can_retry is True
    saved = repository.save_latest_face_attempt.await_args.kwargs
    assert saved["liveness_passed"] is None
    assert saved["validation_status"] == "failed"
    assert saved["failure_reason"] == (
        "Face similarity was below the required threshold"
    )
    repository.mark_verification_attempt_failed.assert_not_awaited()
    session.commit.assert_awaited_once()


def test_existing_pass_rejects_a_new_capture_without_comparing_again() -> None:
    existing = SimpleNamespace(
        attempt_number=2,
        validation_status="passed",
        similarity_score=Decimal("0.75"),
    )
    service, session, repository, comparison_service = build_service(
        existing=existing,
        comparison=FaceComparisonResult(status=FaceComparisonStatus.MATCHED),
    )

    with pytest.raises(
        VerificationClosedError,
        match="already passed",
    ):
        asyncio.run(
            service.verify(
                session_id=SESSION_ID,
                student_id=STUDENT_ID,
                captured_image=b"capture",
                liveness_evidence=VALID_LIVENESS_EVIDENCE,
            )
        )

    comparison_service.compare.assert_not_awaited()
    repository.save_latest_face_attempt.assert_not_awaited()
    session.commit.assert_not_awaited()
