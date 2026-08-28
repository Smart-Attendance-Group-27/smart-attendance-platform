from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from repositories.attendance_face_verification_repository import (
    AttendanceFaceVerificationRepository,
    AttendanceVerificationContext,
)
from repositories.face_profile_repository import FaceProfileRepository
from repositories.verification_config_repository import (
    VerificationConfigRepository,
)
from services.face_comparison_service import (
    FaceComparisonResult,
    FaceComparisonService,
    FaceComparisonStatus,
)


class AttendanceFaceVerificationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    NO_FACE = "no_face"
    MULTIPLE_FACES = "multiple_faces"
    LOW_QUALITY = "low_quality"
    PROCESSING_FAILED = "processing_failed"
    MODEL_MISMATCH = "model_mismatch"
    ATTEMPT_LIMIT_REACHED = "attempt_limit_reached"


@dataclass(frozen=True, slots=True)
class AttendanceFaceVerificationResult:
    status: AttendanceFaceVerificationStatus
    attempt_number: int
    can_retry: bool
    similarity_score: float | None = None
    similarity_threshold: float | None = None
    detection_confidence: float | None = None


class AttendanceFaceVerificationError(RuntimeError):
    pass


class VerificationNotStartedError(AttendanceFaceVerificationError):
    pass


class VerificationClosedError(AttendanceFaceVerificationError):
    pass


class AttendanceFaceVerificationUnavailableError(
    AttendanceFaceVerificationError
):
    pass


Clock = Callable[[], datetime]


class AttendanceFaceVerificationService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        face_comparison_service: FaceComparisonService,
        max_attempts: int,
        repository: AttendanceFaceVerificationRepository | None = None,
        face_profile_repository: FaceProfileRepository | None = None,
        verification_config_repository: VerificationConfigRepository | None = None,
        clock: Clock | None = None,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least one")

        self._session = session
        self._face_comparison_service = face_comparison_service
        self._max_attempts = max_attempts
        self._repository = repository or AttendanceFaceVerificationRepository(
            session
        )
        self._face_profile_repository = (
            face_profile_repository or FaceProfileRepository(session)
        )
        self._verification_config_repository = (
            verification_config_repository
            or VerificationConfigRepository(session)
        )
        self._clock = clock or self._utc_now

    async def verify(
        self,
        *,
        session_id: UUID,
        student_id: UUID,
        captured_image: bytes,
    ) -> AttendanceFaceVerificationResult:
        validated_at = self._ensure_utc(self._clock())

        context = await self._repository.lock_verification_context(
            session_id=session_id,
            student_id=student_id,
        )
        self._validate_context(context, validated_at)
        assert context is not None

        existing = await self._repository.lock_latest_face_attempt(
            context.verification_attempt_id
        )
        if existing is not None and existing.validation_status == "passed":
            return AttendanceFaceVerificationResult(
                status=AttendanceFaceVerificationStatus.PASSED,
                attempt_number=existing.attempt_number,
                can_retry=False,
                similarity_score=(
                    float(existing.similarity_score)
                    if existing.similarity_score is not None
                    else None
                ),
            )

        previous_attempt_number = existing.attempt_number if existing else 0
        if previous_attempt_number >= self._max_attempts:
            return AttendanceFaceVerificationResult(
                status=AttendanceFaceVerificationStatus.ATTEMPT_LIMIT_REACHED,
                attempt_number=previous_attempt_number,
                can_retry=False,
            )

        reference = (
            await self._face_profile_repository.get_stored_embedding_for_comparison(
                student_id
            )
        )
        if reference is None:
            raise AttendanceFaceVerificationUnavailableError(
                "A generated reference face profile is required."
            )

        config = await self._verification_config_repository.get_active()
        if config is None:
            raise AttendanceFaceVerificationUnavailableError(
                "No active face-verification configuration is available."
            )

        attempt_number = previous_attempt_number + 1
        comparison = await self._face_comparison_service.compare(
            reference=reference,
            captured_image=captured_image,
            similarity_threshold=float(config.similarity_threshold),
        )
        passed = comparison.status is FaceComparisonStatus.MATCHED
        can_retry = not passed and attempt_number < self._max_attempts

        await self._repository.save_latest_face_attempt(
            existing=existing,
            verification_attempt_id=context.verification_attempt_id,
            face_profile_id=reference.profile_id,
            attempt_number=attempt_number,
            liveness_passed=self._liveness_passed(comparison),
            quality_passed=self._quality_passed(comparison),
            similarity_score=comparison.similarity_score,
            verification_config_id=config.id,
            validation_status="passed" if passed else "failed",
            failure_reason=(
                None
                if passed
                else self._failure_reason(comparison)
            ),
            captured_at=validated_at,
            validated_at=validated_at,
        )

        if not passed and not can_retry:
            await self._repository.mark_verification_attempt_failed(
                context.verification_attempt_id,
                failure_reason="FACE_ATTEMPT_LIMIT_REACHED",
                completed_at=validated_at,
            )

        await self._session.commit()

        return AttendanceFaceVerificationResult(
            status=self._status_for_comparison(comparison.status),
            attempt_number=attempt_number,
            can_retry=can_retry,
            similarity_score=comparison.similarity_score,
            similarity_threshold=comparison.similarity_threshold,
            detection_confidence=comparison.detection_confidence,
        )

    @staticmethod
    def _validate_context(
        context: AttendanceVerificationContext | None,
        validated_at: datetime,
    ) -> None:
        if context is None:
            raise VerificationNotStartedError(
                "Attendance verification has not started for this session."
            )
        if context.verification_status != "in_progress":
            raise VerificationClosedError(
                "Attendance verification is already closed."
            )
        if (
            context.requires_geofence
            and context.latest_geofence_status != "passed"
        ):
            raise VerificationNotStartedError(
                "Geofence verification must pass before face verification."
            )
        if (
            context.session_status != "active"
            or context.closed_at is not None
            or context.cancelled_at is not None
            or context.requires_face_verification is not True
        ):
            raise VerificationClosedError(
                "Face verification is not available for this session."
            )
        if (
            context.check_in_opens_at is None
            or context.check_in_closes_at is None
            or validated_at < AttendanceFaceVerificationService._ensure_utc(
                context.check_in_opens_at
            )
            or validated_at >= AttendanceFaceVerificationService._ensure_utc(
                context.check_in_closes_at
            )
        ):
            raise VerificationClosedError("The check-in window is closed.")

    @staticmethod
    def _status_for_comparison(
        status: FaceComparisonStatus,
    ) -> AttendanceFaceVerificationStatus:
        if status is FaceComparisonStatus.MATCHED:
            return AttendanceFaceVerificationStatus.PASSED
        if status is FaceComparisonStatus.NOT_MATCHED:
            return AttendanceFaceVerificationStatus.FAILED
        return AttendanceFaceVerificationStatus(status.value)

    @staticmethod
    def _liveness_passed(comparison: FaceComparisonResult) -> bool:
        return comparison.status in {
            FaceComparisonStatus.MATCHED,
            FaceComparisonStatus.NOT_MATCHED,
        }

    @staticmethod
    def _quality_passed(comparison: FaceComparisonResult) -> bool:
        return comparison.status in {
            FaceComparisonStatus.MATCHED,
            FaceComparisonStatus.NOT_MATCHED,
        }

    @staticmethod
    def _failure_reason(comparison: FaceComparisonResult) -> str:
        reason = comparison.failure_reason or comparison.status.value
        return reason[:100]

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _ensure_utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Face-verification timestamps must include a timezone")
        return value.astimezone(UTC)


__all__ = [
    "AttendanceFaceVerificationError",
    "AttendanceFaceVerificationResult",
    "AttendanceFaceVerificationService",
    "AttendanceFaceVerificationStatus",
    "AttendanceFaceVerificationUnavailableError",
    "VerificationClosedError",
    "VerificationNotStartedError",
]
