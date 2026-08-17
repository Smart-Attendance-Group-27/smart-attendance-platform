from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from modules.academic.admin_dashboard.schemas import AdminOverviewResponse
from modules.academic.admin_dashboard.service import AdminDashboardService
from modules.identity.auth.dependencies import CurrentAdministrator

router = APIRouter(prefix="/administrators/me", tags=["admin-dashboard"])


def get_admin_dashboard_service() -> AdminDashboardService:
    return AdminDashboardService()


@router.get(
    "/dashboard-overview",
    response_model=AdminOverviewResponse,
    status_code=status.HTTP_200_OK,
)
async def get_admin_dashboard_overview(
    http_request: Request,
    current_administrator: CurrentAdministrator,
    dashboard_service: Annotated[
        AdminDashboardService,
        Depends(get_admin_dashboard_service),
    ] = None,  # type: ignore[assignment]
) -> AdminOverviewResponse:
    overview = await dashboard_service.get_overview(http_request.app.state.db_pool)
    return AdminOverviewResponse.from_record(overview)
