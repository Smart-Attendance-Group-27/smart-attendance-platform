from dataclasses import dataclass
from uuid import UUID

import httpx

# face-verification service ask the Core Backend

class CoreApiStudentProfileError(RuntimeError):
    """Base class for safe Core Backend profile lookup failures."""


class CoreApiUnauthorizedError(CoreApiStudentProfileError):
    """The Core Backend rejected the bearer token."""


class CoreApiForbiddenError(CoreApiStudentProfileError):
    """The authenticated caller is not permitted to act as a student."""


class CoreApiStudentProfileNotFoundError(CoreApiStudentProfileError):
    """The caller has no active student profile."""


class CoreApiUnavailableError(CoreApiStudentProfileError):
    """The Core Backend could not provide a trustworthy profile response."""


@dataclass(frozen=True, slots=True)
class CoreApiStudentProfile:
    id: UUID


class CoreApiStudentProfileClient:
    """Resolve the bearer token through the Core Backend's `/me` endpoint."""

    def __init__(self,*,base_url: str,timeout_seconds: float,transport: httpx.AsyncBaseTransport | None = None,) -> None:
        self._client = httpx.AsyncClient(base_url=base_url,timeout=timeout_seconds,transport=transport,)

    async def get_current_student_profile(self,access_token: str,) -> CoreApiStudentProfile:
        try:
            response = await self._client.get("/api/v1/students/me/profile",headers={"Authorization": f"Bearer {access_token}"},)
            
        except httpx.HTTPError as error:
            raise CoreApiUnavailableError() from error

        if response.status_code == 401:
            raise CoreApiUnauthorizedError()

        if response.status_code == 403:
            raise CoreApiForbiddenError()

        if response.status_code == 404:
            raise CoreApiStudentProfileNotFoundError()

        if response.status_code != 200:
            raise CoreApiUnavailableError()

        try:
            profile_id = UUID(response.json()["id"])
        except (KeyError, TypeError, ValueError) as error:
            raise CoreApiUnavailableError() from error

        return CoreApiStudentProfile(id=profile_id)

    async def close(self) -> None:
        await self._client.aclose()


__all__ = [
    "CoreApiForbiddenError",
    "CoreApiStudentProfile",
    "CoreApiStudentProfileClient",
    "CoreApiStudentProfileNotFoundError",
    "CoreApiUnauthorizedError",
    "CoreApiUnavailableError",
]
