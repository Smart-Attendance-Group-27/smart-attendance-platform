from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from modules.academic.lecturer_correction_requests.exception import (
    CorrectionRequestInvalidError,
    CorrectionTargetNotFoundError,
)
from modules.academic.lecturer_correction_requests.schemas import (
    CorrectionRequestResponse,
    CreateCorrectionRequestBody,
)
from modules.academic.lecturer_correction_requests.service import CorrectionRequestService
from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.identity.auth.dependencies import CurrentLecturer

router = APIRouter(prefix="/lecturers", tags=["lecturer-correction-requests"])


def get_correction_request_service() -> CorrectionRequestService:
    return CorrectionRequestService()


@router.post(
    "/me/correction-requests",
    response_model=CorrectionRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_correction_request(
    body: CreateCorrectionRequestBody,
    http_request: Request,
    current_lecturer: CurrentLecturer,
    service: Annotated[
        CorrectionRequestService,
        Depends(get_correction_request_service),
    ] = None,  # type: ignore[assignment]
) -> CorrectionRequestResponse:
    # The requester comes from the verified token only; a course or timetable
    # entry the lecturer is not assigned to is reported as not found.
    try:
        record = await service.submit(
            http_request.app.state.db_pool,
            user_id=current_lecturer.user_id,
            request_type=body.request_type,
            category=body.category,
            course_offering_id=body.course_offering_id,
            timetable_entry_id=body.timetable_entry_id,
            description=body.description,
        )
    except LecturerProfileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "LECTURER_PROFILE_NOT_FOUND",
                "message": "An active lecturer profile was not found for this account.",
            },
        ) from error
    except CorrectionTargetNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "CORRECTION_TARGET_NOT_FOUND",
                "message": "That course or timetable entry is not assigned to you.",
            },
        ) from error
    except CorrectionRequestInvalidError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "CORRECTION_REQUEST_INVALID", "message": str(error)},
        ) from error

    return CorrectionRequestResponse(
        id=record.id,
        request_type=record.request_type,
        category=record.category,
        course_offering_id=record.course_offering_id,
        timetable_entry_id=record.timetable_entry_id,
        status=record.status,
    )
