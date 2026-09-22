from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from core.errors import error_detail
from modules.attendance_verification.check_in.exception import (
    ActiveStudentProfileNotFoundError,
    AttendanceSessionNotFoundError,
    VerificationNotStartedError,
)
from modules.attendance_verification.check_in.schemas import CheckInResponse
from modules.attendance_verification.check_in.service import CheckInService
from modules.identity.auth.dependencies import CurrentStudent

router = APIRouter(
    prefix="/attendance-sessions/{session_id}/check-in",
    tags=["check-in"],
)


def get_check_in_service() -> CheckInService:
    return CheckInService()


@router.post("", response_model=CheckInResponse, status_code=status.HTTP_200_OK)
async def check_in(
    session_id: UUID,
    http_request: Request,
    current_student: CurrentStudent,
    check_in_service: Annotated[
        CheckInService,
        Depends(get_check_in_service),
    ] = None,  # type: ignore[assignment]
) -> CheckInResponse:
    """Check the student in, or report what is still missing.

    Idempotent: calling it again once checked in returns the same check-in with
    the same timestamp rather than moving it.
    """

    try:
        result = await check_in_service.check_in_for_user(
            http_request.app.state.db_pool,
            current_student.user_id,
            session_id,
        )
    except ActiveStudentProfileNotFoundError as error:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            error_detail("STUDENT_PROFILE_NOT_FOUND", error.message),
        ) from error
    except AttendanceSessionNotFoundError as error:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            error_detail("SESSION_NOT_FOUND", error.message),
        ) from error
    except VerificationNotStartedError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            error_detail("VERIFICATION_NOT_STARTED", error.message),
        ) from error

    return CheckInResponse.from_result(result)
