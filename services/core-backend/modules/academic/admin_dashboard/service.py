import asyncpg

from modules.academic.admin_dashboard.repository import AdminDashboardRepository, AdminOverviewRecord


class AdminDashboardService:
    def __init__(self, repository: AdminDashboardRepository | None = None) -> None:
        self._repository = repository or AdminDashboardRepository()

    async def get_overview(self, pool: asyncpg.Pool) -> AdminOverviewRecord:
        async with pool.acquire() as connection:
            return await self._repository.get_overview(connection)
