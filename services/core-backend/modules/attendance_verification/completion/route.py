from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from modules.attendance_verification.check_in.exception import (
    ActiveStudentProfileNotFoundError,
    AttendanceSessionNotFoundError,
    VerificationNotStartedError,
)
from modules.attendance_verification.check_in.route import get_check_in_service
from modules.attendance_verification.check_in.service import CheckInService
from modules.attendance_verification.completion.schemas import CompleteCheckInResponse
from modules.identity.auth.dependencies import CurrentStudent

router = APIRouter(
    prefix="/attendance-sessions/{session_id}/complete-check-in",
    tags=["check-in-completion"],
)


@router.post(
    "",
    response_model=CompleteCheckInResponse,
    status_code=status.HTTP_200_OK,
    deprecated=True,
)
async def complete_check_in(
    session_id: UUID,
    http_request: Request,
    current_student: CurrentStudent,
    check_in_service: Annotated[
        CheckInService,
        Depends(get_check_in_service),
    ] = None,  # type: ignore[assignment]
) -> CompleteCheckInResponse:
    """Deprecated alias for ``POST .../check-in``.

    Same work, old response shape, so a phone running the shipped build keeps
    checking in while the new client rolls out. The one behaviour that changed
    is the one that was wrong: this no longer writes an attendance record, since
    attendance is decided when the lecturer closes the session.

    Removed by INT-5, once the mobile and web clients have moved over.
    """

    try:
        result = await check_in_service.check_in_for_user(
            http_request.app.state.db_pool,
            current_student.user_id,
            session_id,
        )
    except ActiveStudentProfileNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, error.message) from error
    except AttendanceSessionNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, error.message) from error
    except VerificationNotStartedError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, error.message) from error

    return CompleteCheckInResponse.from_check_in(result)
