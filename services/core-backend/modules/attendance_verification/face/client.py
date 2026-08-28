from dataclasses import dataclass
from typing import Literal
from uuid import UUID

import httpx


InternalFaceStatus = Literal[
    "passed",
    "failed",
    "no_face",
    "multiple_faces",
    "low_quality",
    "processing_failed",
    "model_mismatch",
    "attempt_limit_reached",
]


@dataclass(frozen=True, slots=True)
class InternalFaceVerificationResult:
    status: InternalFaceStatus
    attempt_number: int
    can_retry: bool


class FaceVerificationServiceError(RuntimeError):
    pass


class FaceVerificationServiceRejectedError(FaceVerificationServiceError):
    pass


class FaceVerificationServiceClient:
    def __init__(self, *, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    async def verify_attendance_face(
        self,
        *,
        session_id: UUID,
        access_token: str,
        image: bytes,
        content_type: str,
    ) -> InternalFaceVerificationResult:
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(
                    f"{self._base_url}/internal/v1/attendance-sessions/"
                    f"{session_id}/face-verifications",
                    headers={"Authorization": f"Bearer {access_token}"},
                    files={"image": ("capture.jpg", image, content_type)},
                )
        except httpx.HTTPError as error:
            raise FaceVerificationServiceError(
                "The face-verification service is unavailable."
            ) from error

        if response.status_code in {404, 409}:
            raise FaceVerificationServiceRejectedError(
                "Face verification cannot continue for this session."
            )
        if response.status_code != 200:
            raise FaceVerificationServiceError(
                "The face-verification service returned an invalid response."
            )

        try:
            payload = response.json()
        except ValueError as error:
            raise FaceVerificationServiceError(
                "The face-verification service returned invalid JSON."
            ) from error

        result = self._parse_result(payload)
        if result is None:
            raise FaceVerificationServiceError(
                "The face-verification service returned an invalid result."
            )
        return result

    @staticmethod
    def _parse_result(value: object) -> InternalFaceVerificationResult | None:
        if not isinstance(value, dict):
            return None

        allowed_statuses: set[str] = {
            "passed",
            "failed",
            "no_face",
            "multiple_faces",
            "low_quality",
            "processing_failed",
            "model_mismatch",
            "attempt_limit_reached",
        }
        status_value = value.get("status")
        attempt_number = value.get("attemptNumber")
        can_retry = value.get("canRetry")
        if (
            not isinstance(status_value, str)
            or status_value not in allowed_statuses
            or not isinstance(attempt_number, int)
            or isinstance(attempt_number, bool)
            or attempt_number < 1
            or not isinstance(can_retry, bool)
        ):
            return None

        return InternalFaceVerificationResult(
            status=status_value,  # type: ignore[arg-type]
            attempt_number=attempt_number,
            can_retry=can_retry,
        )


__all__ = [
    "FaceVerificationServiceClient",
    "FaceVerificationServiceError",
    "FaceVerificationServiceRejectedError",
    "InternalFaceVerificationResult",
]
