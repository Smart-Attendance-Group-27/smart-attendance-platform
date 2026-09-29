import asyncpg

from modules.academic.admin_reference_faces.repository import (
    AdminReferenceFaceRepository,
    ReferenceFaceRecord,
)
from modules.academic.admin_reference_faces.client import (
    ReferenceFaceEnrollmentClient,
    ReferenceFaceEnrollmentPhoto,
    ReferenceFaceEnrollmentResult,
)


class AdminReferenceFaceService:
    def __init__(
        self,
        repository: AdminReferenceFaceRepository | None = None,
        enrollment_client: ReferenceFaceEnrollmentClient | None = None,
    ) -> None:
        self._repository = repository or AdminReferenceFaceRepository()
        self._enrollment_client = enrollment_client

    async def list_reference_faces(self, pool: asyncpg.Pool) -> list[ReferenceFaceRecord]:
        async with pool.acquire() as connection:
            return await self._repository.list_reference_faces(connection)

    async def enroll_uploaded_reference_faces(
        self,
        *,
        photos: list[ReferenceFaceEnrollmentPhoto],
        access_token: str,
    ) -> ReferenceFaceEnrollmentResult:
        if self._enrollment_client is None:
            raise RuntimeError("Reference-face enrolment is not configured")
        return await self._enrollment_client.enroll_uploads(
            photos=photos,
            access_token=access_token,
        )
