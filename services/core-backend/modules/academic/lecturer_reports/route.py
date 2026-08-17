from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.academic.lecturer_reports.exception import CourseOfferingNotFoundError
from modules.academic.lecturer_reports.schemas import (
    CourseSessionReportResponse,
    LecturerDashboardOverviewResponse,
)
from modules.academic.lecturer_reports.service import LecturerReportService
from modules.identity.auth.dependencies import CurrentLecturer

router = APIRouter(prefix="/lecturers/me", tags=["lecturer-reports"])

_PROFILE_NOT_FOUND_DETAIL = "An active lecturer profile was not found for this account."
_COURSE_NOT_FOUND_DETAIL = "The course offering was not found."


def get_lecturer_report_service() -> LecturerReportService:
    return LecturerReportService()


@router.get(
    "/dashboard-overview",
    response_model=LecturerDashboardOverviewResponse,
    status_code=status.HTTP_200_OK,
)
async def get_my_dashboard_overview(
    http_request: Request,
    current_lecturer: CurrentLecturer,
    report_service: Annotated[
        LecturerReportService,
        Depends(get_lecturer_report_service),
    ] = None,  # type: ignore[assignment]
) -> LecturerDashboardOverviewResponse:
    try:
        overview = await report_service.get_overview_for_user(
            http_request.app.state.db_pool,
            current_lecturer.user_id,
        )
    except LecturerProfileNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _PROFILE_NOT_FOUND_DETAIL) from error

    return LecturerDashboardOverviewResponse.from_record(overview)


@router.get(
    "/reports/courses/{course_offering_id}",
    response_model=list[CourseSessionReportResponse],
    status_code=status.HTTP_200_OK,
)
async def get_my_course_session_report(
    course_offering_id: UUID,
    http_request: Request,
    current_lecturer: CurrentLecturer,
    report_service: Annotated[
        LecturerReportService,
        Depends(get_lecturer_report_service),
    ] = None,  # type: ignore[assignment]
) -> list[CourseSessionReportResponse]:
    try:
        report = await report_service.get_course_session_report_for_user(
            http_request.app.state.db_pool,
            current_lecturer.user_id,
            course_offering_id,
        )
    except LecturerProfileNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _PROFILE_NOT_FOUND_DETAIL) from error
    except CourseOfferingNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _COURSE_NOT_FOUND_DETAIL) from error

    return [CourseSessionReportResponse.from_record(item) for item in report]
