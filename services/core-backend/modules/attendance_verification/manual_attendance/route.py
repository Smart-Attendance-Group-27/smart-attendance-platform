from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.attendance_verification.manual_attendance.exception import (
    ManualReasonInvalidError,
    SessionCancelledError,
    SessionNotFoundError,
    SessionNotStartedError,
    StudentNotOnRosterError,
)
from modules.attendance_verification.manual_attendance.schemas import (
    ManualAttendanceResponse,
    SetManualAttendanceRequest,
)
from modules.attendance_verification.manual_attendance.service import ManualAttendanceService
from modules.contracts.providers import get_notification_producer
from modules.identity.auth.dependencies import CurrentLecturer

# Included into the lecturer sessions router, which supplies the
# /lecturers/me/attendance-sessions prefix.
router = APIRouter(tags=["manual-attendance"])


def get_manual_attendance_service() -> ManualAttendanceService:
    return ManualAttendanceService(notification_producer=get_notification_producer())


def _error(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


@router.put(
    "/{session_id}/students/{student_id}/attendance",
    response_model=ManualAttendanceResponse,
    status_code=status.HTTP_200_OK,
)
async def set_student_attendance(
    session_id: UUID,
    student_id: UUID,
    body: SetManualAttendanceRequest,
    http_request: Request,
    current_lecturer: CurrentLecturer,
    service: Annotated[
        ManualAttendanceService,
        Depends(get_manual_attendance_service),
    ] = None,  # type: ignore[assignment]
) -> ManualAttendanceResponse:
    try:
        result = await service.set_status(
            http_request.app.state.db_pool,
            lecturer_user_id=current_lecturer.user_id,
            session_id=session_id,
            student_id=student_id,
            status=body.status,
            reason=body.reason,
        )
    except LecturerProfileNotFoundError as error:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            _error(
                "LECTURER_PROFILE_NOT_FOUND",
                "An active lecturer profile was not found for this account.",
            ),
        ) from error
    except SessionNotFoundError as error:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            _error("SESSION_NOT_FOUND", "The attendance session was not found."),
        ) from error
    except StudentNotOnRosterError as error:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            _error("STUDENT_NOT_ON_ROSTER", "The student is not on this session's roster."),
        ) from error
    except SessionNotStartedError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            _error("SESSION_NOT_STARTED", "The session has not started yet."),
        ) from error
    except SessionCancelledError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            _error("SESSION_CANCELLED", "The session was cancelled."),
        ) from error
    except ManualReasonInvalidError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            _error("REASON_INVALID", "A reason of 3 to 500 characters is required."),
        ) from error

    return ManualAttendanceResponse.from_result(result)
