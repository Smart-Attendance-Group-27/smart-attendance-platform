import asyncpg

from modules.audit.admin_log.repository import (
    DEFAULT_LIST_LIMIT,
    AuditLogRecord,
    AuditLogRepository,
)


class AuditLogService:
    def __init__(self, repository: AuditLogRepository | None = None) -> None:
        self._repository = repository or AuditLogRepository()

    async def list_audit_logs(
        self,
        pool: asyncpg.Pool,
        *,
        limit: int = DEFAULT_LIST_LIMIT,
    ) -> list[AuditLogRecord]:
        async with pool.acquire() as connection:
            return await self._repository.list_audit_logs(connection, limit=limit)
