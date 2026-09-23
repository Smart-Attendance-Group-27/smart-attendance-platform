import asyncio
from dataclasses import replace
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
    repository.get_verification_context.return_value = build_context()
    repository.lock_verification_context.return_value = build_context()
    repository.get_latest_face_attempt.return_value = existing
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
    saved = repository.record_face_attempt.await_args.kwargs
    assert saved["attempt_number"] == 1
    assert saved["liveness_passed"] is True
    assert saved["validation_status"] == "passed"
    repository.mark_verification_attempt_failed.assert_not_awaited()
    assert session.commit.await_count == 2


def test_no_face_consumes_retry_and_appends_a_new_record() -> None:
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
    saved = repository.record_face_attempt.await_args.kwargs
    assert saved["attempt_number"] == 2
    repository.mark_verification_attempt_failed.assert_not_awaited()


def test_matched_retry_consumes_attempt_and_preserves_previous_failure() -> None:
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
    saved = repository.record_face_attempt.await_args.kwargs
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
    saved = repository.record_face_attempt.await_args.kwargs
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
    saved = repository.record_face_attempt.await_args.kwargs
    assert saved["attempt_number"] == 2
    repository.mark_verification_attempt_failed.assert_not_awaited()
    assert session.commit.await_count == 2


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
    repository.record_face_attempt.assert_not_awaited()
    repository.mark_verification_attempt_failed.assert_not_awaited()
    session.commit.assert_awaited_once()


def test_missing_liveness_is_rejected_before_database_access() -> None:
    service, session, repository, _ = build_service(
        comparison=FaceComparisonResult(
            status=FaceComparisonStatus.MATCHED,
            similarity_score=0.82,
            similarity_threshold=0.5,
        )
    )

    with pytest.raises(ValueError, match="Liveness evidence is required"):
        asyncio.run(
            service.verify(
                session_id=SESSION_ID,
                student_id=STUDENT_ID,
                captured_image=b"capture",
                liveness_evidence=None,  # type: ignore[arg-type]
            )
        )

    repository.get_verification_context.assert_not_awaited()
    repository.record_face_attempt.assert_not_awaited()
    session.commit.assert_not_awaited()


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
    repository.record_face_attempt.assert_not_awaited()
    session.commit.assert_not_awaited()


def test_fail_fail_pass_keeps_three_append_only_attempts() -> None:
    class AppendOnlyRepository:
        def __init__(self) -> None:
            self.records: list[SimpleNamespace] = []

        async def lock_verification_context(self, **_kwargs):
            return build_context()

        async def get_verification_context(self, **_kwargs):
            return build_context()

        async def lock_latest_face_attempt(self, _verification_attempt_id):
            return self.records[-1] if self.records else None

        async def get_latest_face_attempt(self, _verification_attempt_id):
            return self.records[-1] if self.records else None

        async def record_face_attempt(self, **values):
            record = SimpleNamespace(**values)
            self.records.append(record)
            return record

        async def mark_verification_attempt_failed(self, *_args, **_kwargs):
            return None

    repository = AppendOnlyRepository()
    session = AsyncMock()
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
    comparison_service.compare.side_effect = [
        FaceComparisonResult(
            status=FaceComparisonStatus.NOT_MATCHED,
            failure_reason="Not matched",
        ),
        FaceComparisonResult(
            status=FaceComparisonStatus.NO_FACE,
            failure_reason="No face",
        ),
        FaceComparisonResult(
            status=FaceComparisonStatus.MATCHED,
            similarity_score=0.82,
            similarity_threshold=0.5,
        ),
    ]
    service = AttendanceFaceVerificationService(
        session=session,
        face_comparison_service=comparison_service,
        max_attempts=3,
        repository=repository,  # type: ignore[arg-type]
        face_profile_repository=face_profiles,
        verification_config_repository=configs,
        clock=lambda: NOW,
    )

    results = [
        asyncio.run(
            service.verify(
                session_id=SESSION_ID,
                student_id=STUDENT_ID,
                captured_image=b"capture",
                liveness_evidence=VALID_LIVENESS_EVIDENCE,
            )
        )
        for _ in range(3)
    ]

    assert [result.attempt_number for result in results] == [1, 2, 3]
    assert [record.attempt_number for record in repository.records] == [1, 2, 3]
    assert [record.validation_status for record in repository.records] == [
        "failed",
        "failed",
        "passed",
    ]


def test_inference_runs_after_the_snapshot_transaction_ends() -> None:
    service, session, repository, comparison_service = build_service(
        comparison=FaceComparisonResult(
            status=FaceComparisonStatus.MATCHED,
            similarity_score=0.82,
            similarity_threshold=0.5,
        )
    )

    async def compare(**_kwargs):
        assert session.commit.await_count == 1
        repository.lock_verification_context.assert_not_awaited()
        return FaceComparisonResult(
            status=FaceComparisonStatus.MATCHED,
            similarity_score=0.82,
            similarity_threshold=0.5,
        )

    comparison_service.compare.side_effect = compare

    asyncio.run(
        service.verify(
            session_id=SESSION_ID,
            student_id=STUDENT_ID,
            captured_image=b"capture",
            liveness_evidence=VALID_LIVENESS_EVIDENCE,
        )
    )

    assert session.commit.await_count == 2


def test_session_closed_during_inference_is_rejected_before_persistence() -> None:
    service, session, repository, comparison_service = build_service(
        comparison=FaceComparisonResult(status=FaceComparisonStatus.MATCHED)
    )
    repository.lock_verification_context.return_value = replace(
        build_context(),
        session_status="closed",
        closed_at=NOW + timedelta(seconds=1),
    )

    with pytest.raises(VerificationClosedError, match="not available"):
        asyncio.run(
            service.verify(
                session_id=SESSION_ID,
                student_id=STUDENT_ID,
                captured_image=b"capture",
                liveness_evidence=VALID_LIVENESS_EVIDENCE,
            )
        )

    comparison_service.compare.assert_awaited_once()
    repository.record_face_attempt.assert_not_awaited()
    session.commit.assert_awaited_once()


def test_concurrent_pass_is_rejected_after_inference() -> None:
    service, session, repository, comparison_service = build_service(
        comparison=FaceComparisonResult(status=FaceComparisonStatus.MATCHED)
    )
    repository.lock_latest_face_attempt.return_value = SimpleNamespace(
        attempt_number=1,
        validation_status="passed",
    )

    with pytest.raises(VerificationClosedError, match="already passed"):
        asyncio.run(
            service.verify(
                session_id=SESSION_ID,
                student_id=STUDENT_ID,
                captured_image=b"capture",
                liveness_evidence=VALID_LIVENESS_EVIDENCE,
            )
        )

    comparison_service.compare.assert_awaited_once()
    repository.record_face_attempt.assert_not_awaited()
    session.commit.assert_awaited_once()


def test_concurrent_attempt_limit_discards_inference_result() -> None:
    initial = SimpleNamespace(attempt_number=2, validation_status="failed")
    service, session, repository, comparison_service = build_service(
        existing=initial,
        comparison=FaceComparisonResult(status=FaceComparisonStatus.NOT_MATCHED),
    )
    repository.lock_latest_face_attempt.return_value = SimpleNamespace(
        attempt_number=3,
        validation_status="failed",
    )

    result = asyncio.run(
        service.verify(
            session_id=SESSION_ID,
            student_id=STUDENT_ID,
            captured_image=b"capture",
            liveness_evidence=VALID_LIVENESS_EVIDENCE,
        )
    )

    assert result.status is AttendanceFaceVerificationStatus.ATTEMPT_LIMIT_REACHED
    assert result.attempt_number == 3
    assert result.can_retry is False
    comparison_service.compare.assert_awaited_once()
    repository.record_face_attempt.assert_not_awaited()
    session.rollback.assert_awaited_once()
