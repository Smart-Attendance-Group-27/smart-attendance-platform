from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from modules.attendance_verification.completion.exception import (
    ActiveStudentProfileNotFoundError,
    AttendanceSessionNotFoundError,
    VerificationNotStartedError,
)
from modules.attendance_verification.completion.schemas import CompleteCheckInResponse
from modules.attendance_verification.completion.service import CompletionService
from modules.identity.auth.dependencies import CurrentStudent

router = APIRouter(
    prefix="/attendance-sessions/{session_id}/complete-check-in",
    tags=["check-in-completion"],
)


def get_completion_service() -> CompletionService:
    return CompletionService()


@router.post("", response_model=CompleteCheckInResponse, status_code=status.HTTP_200_OK)
async def complete_check_in(
    session_id: UUID,
    http_request: Request,
    current_student: CurrentStudent,
    completion_service: Annotated[
        CompletionService,
        Depends(get_completion_service),
    ] = None,  # type: ignore[assignment]
) -> CompleteCheckInResponse:
    try:
        result = await completion_service.complete_for_user(
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

    return CompleteCheckInResponse.from_result(result)
