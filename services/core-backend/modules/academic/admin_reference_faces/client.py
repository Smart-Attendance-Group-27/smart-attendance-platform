from dataclasses import dataclass
from typing import BinaryIO

import httpx


class ReferenceFaceEnrollmentClientError(RuntimeError):
    pass


class ReferenceFaceEnrollmentUploadError(ReferenceFaceEnrollmentClientError):
    pass


class ReferenceFaceEnrollmentBusyError(ReferenceFaceEnrollmentClientError):
    pass


@dataclass(frozen=True, slots=True)
class ReferenceFaceEnrollmentResult:
    discovered: int
    enrolled: int
    already_enrolled: int
    skipped: int
    failed: int


@dataclass(frozen=True, slots=True)
class ReferenceFaceEnrollmentPhoto:
    filename: str
    content_type: str
    file: BinaryIO


class ReferenceFaceEnrollmentClient:
    def __init__(self, *, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    async def enroll_uploads(
        self,
        *,
        photos: list[ReferenceFaceEnrollmentPhoto],
        access_token: str,
    ) -> ReferenceFaceEnrollmentResult:
        multipart_files = [
            ("images", (photo.filename, photo.file, photo.content_type))
            for photo in photos
        ]
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(
                    f"{self._base_url}/internal/v1/reference-faces/enrolments/upload",
                    headers={"Authorization": f"Bearer {access_token}"},
                    files=multipart_files,
                )
        except httpx.HTTPError as error:
            raise ReferenceFaceEnrollmentClientError(
                "The face-verification service is unavailable."
            ) from error

        if response.status_code in {400, 404, 413, 415, 422}:
            raise ReferenceFaceEnrollmentUploadError(_safe_detail(response))
        if response.status_code == 409:
            raise ReferenceFaceEnrollmentBusyError(_safe_detail(response))
        if response.status_code != 200:
            raise ReferenceFaceEnrollmentClientError(
                "The face-verification service could not complete enrolment."
            )
        return _parse_result(response)


def _safe_detail(response: httpx.Response) -> str:
    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        detail = None
    return detail if isinstance(detail, str) else "The enrolment upload is not valid."


def _required_count(payload: object, key: str) -> int:
    if not isinstance(payload, dict):
        raise ValueError(f"Missing {key}")
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"Invalid {key}")
    return value


def _parse_result(response: httpx.Response) -> ReferenceFaceEnrollmentResult:
    try:
        payload = response.json()
        return ReferenceFaceEnrollmentResult(
            discovered=_required_count(payload, "discovered"),
            enrolled=_required_count(payload, "enrolled"),
            already_enrolled=_required_count(payload, "alreadyEnrolled"),
            skipped=_required_count(payload, "skipped"),
            failed=_required_count(payload, "failed"),
        )
    except (TypeError, ValueError) as error:
        raise ReferenceFaceEnrollmentClientError(
            "The face-verification service returned an invalid response."
        ) from error


__all__ = [
    "ReferenceFaceEnrollmentBusyError",
    "ReferenceFaceEnrollmentClient",
    "ReferenceFaceEnrollmentClientError",
    "ReferenceFaceEnrollmentUploadError",
    "ReferenceFaceEnrollmentPhoto",
    "ReferenceFaceEnrollmentResult",
]
