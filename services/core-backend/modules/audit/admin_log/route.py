from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from modules.audit.admin_log.repository import DEFAULT_LIST_LIMIT
from modules.audit.admin_log.schemas import AuditLogEntryResponse
from modules.audit.admin_log.service import AuditLogService
from modules.identity.auth.dependencies import CurrentAdministrator

router = APIRouter(prefix="/administrators/me", tags=["admin-audit-log"])


def get_audit_log_service() -> AuditLogService:
    return AuditLogService()


@router.get(
    "/audit-logs",
    response_model=list[AuditLogEntryResponse],
    status_code=status.HTTP_200_OK,
)
async def list_audit_logs(
    http_request: Request,
    current_administrator: CurrentAdministrator,
    limit: int = Query(default=DEFAULT_LIST_LIMIT, ge=1, le=500),
    audit_log_service: Annotated[
        AuditLogService,
        Depends(get_audit_log_service),
    ] = None,  # type: ignore[assignment]
) -> list[AuditLogEntryResponse]:
    records = await audit_log_service.list_audit_logs(http_request.app.state.db_pool, limit=limit)
    return [AuditLogEntryResponse.from_record(record) for record in records]
