from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from modules.academic.admin_institution_reports.schemas import InstitutionReportsResponse
from modules.academic.admin_institution_reports.service import AdminInstitutionReportService
from modules.identity.auth.dependencies import CurrentAdministrator

router = APIRouter(prefix="/administrators/me", tags=["admin-institution-reports"])


def get_admin_institution_report_service() -> AdminInstitutionReportService:
    return AdminInstitutionReportService()


@router.get(
    "/institution-reports",
    response_model=InstitutionReportsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_institution_reports(
    http_request: Request,
    current_administrator: CurrentAdministrator,
    report_service: Annotated[
        AdminInstitutionReportService,
        Depends(get_admin_institution_report_service),
    ] = None,  # type: ignore[assignment]
) -> InstitutionReportsResponse:
    reports = await report_service.get_reports(http_request.app.state.db_pool)
    return InstitutionReportsResponse.from_reports(reports)
