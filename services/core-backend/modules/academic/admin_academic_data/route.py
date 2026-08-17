from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from modules.academic.admin_academic_data.schemas import AdminAcademicDataResponse
from modules.academic.admin_academic_data.service import AdminAcademicDataService
from modules.identity.auth.dependencies import CurrentAdministrator

router = APIRouter(prefix="/administrators/me", tags=["admin-academic-data"])


def get_admin_academic_data_service() -> AdminAcademicDataService:
    return AdminAcademicDataService()


@router.get(
    "/academic-data",
    response_model=AdminAcademicDataResponse,
    status_code=status.HTTP_200_OK,
)
async def get_academic_data(
    http_request: Request,
    current_administrator: CurrentAdministrator,
    academic_data_service: Annotated[
        AdminAcademicDataService,
        Depends(get_admin_academic_data_service),
    ] = None,  # type: ignore[assignment]
) -> AdminAcademicDataResponse:
    data = await academic_data_service.get_academic_data(http_request.app.state.db_pool)
    return AdminAcademicDataResponse.from_data(data)
