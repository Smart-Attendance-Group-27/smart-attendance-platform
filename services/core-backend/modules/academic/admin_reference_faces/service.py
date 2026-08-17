import asyncpg

from modules.academic.admin_reference_faces.repository import (
    AdminReferenceFaceRepository,
    ReferenceFaceRecord,
)


class AdminReferenceFaceService:
    def __init__(self, repository: AdminReferenceFaceRepository | None = None) -> None:
        self._repository = repository or AdminReferenceFaceRepository()

    async def list_reference_faces(self, pool: asyncpg.Pool) -> list[ReferenceFaceRecord]:
        async with pool.acquire() as connection:
            return await self._repository.list_reference_faces(connection)
