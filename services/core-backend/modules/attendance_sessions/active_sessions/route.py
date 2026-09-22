from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from modules.academic.student_profile.exception import StudentProfileNotFoundError
from modules.attendance_sessions.active_sessions.schemas import (
    ActiveAttendanceSessionResponse,
    StudentAttendanceStateResponse,
)
from modules.attendance_sessions.active_sessions.service import (
    ActiveAttendanceSessionService,
)
from modules.attendance_sessions.active_sessions.state_service import (
    SessionNotFoundError,
    StudentAttendanceStateService,
)
from modules.identity.auth.dependencies import CurrentStudent

router = APIRouter(
    prefix="/students/me/attendance-sessions",
    tags=["attendance-sessions"],
)


def get_active_attendance_session_service() -> ActiveAttendanceSessionService:
    return ActiveAttendanceSessionService()


def get_student_attendance_state_service() -> StudentAttendanceStateService:
    return StudentAttendanceStateService()


@router.get(
    "/active",
    response_model=list[ActiveAttendanceSessionResponse],
    status_code=status.HTTP_200_OK,
)
async def list_my_active_attendance_sessions(
    http_request: Request,
    current_student: CurrentStudent,
    session_service: Annotated[
        ActiveAttendanceSessionService,
        Depends(get_active_attendance_session_service),
    ] = None,  # type: ignore[assignment]
) -> list[ActiveAttendanceSessionResponse]:
    try:
        sessions = await session_service.list_for_user(
            http_request.app.state.db_pool,
            current_student.user_id,
        )
    except StudentProfileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "STUDENT_PROFILE_NOT_FOUND",
                "message": "An active student profile was not found for this account.",
            },
        ) from error

    return [
        ActiveAttendanceSessionResponse(
            id=session.id,
            course_code=session.course_code or "",
            course_name=session.course_name or "",
            session_title=session.session_title or "",
            session_type=session.session_type or "",
            lecturer_names=session.lecturer_names,
            scheduled_start_at=session.scheduled_start_at,
            scheduled_end_at=session.scheduled_end_at,
            check_in_opens_at=session.check_in_opens_at,
            check_in_closes_at=session.check_in_closes_at,
            late_after_at=session.late_after_at,
            venue=session.venue,
            requires_face_verification=session.requires_face_verification,
            requires_geofence=session.requires_geofence,
            requires_qr=session.requires_qr,
            attempt_status=session.attempt_status,
            initial_check_in_status=session.initial_check_in_status,
            checked_in_at=session.checked_in_at,
            final_attendance_status=session.final_attendance_status,
        )
        for session in sessions
    ]


@router.get(
    "/{session_id}/attendance",
    response_model=StudentAttendanceStateResponse,
    status_code=status.HTTP_200_OK,
)
async def get_my_attendance_state(
    session_id: UUID,
    http_request: Request,
    current_student: CurrentStudent,
    state_service: Annotated[
        StudentAttendanceStateService,
        Depends(get_student_attendance_state_service),
    ] = None,  # type: ignore[assignment]
) -> StudentAttendanceStateResponse:
    try:
        state = await state_service.get_for_user(
            http_request.app.state.db_pool,
            current_student.user_id,
            session_id,
        )
    except StudentProfileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "STUDENT_PROFILE_NOT_FOUND",
                "message": "An active student profile was not found for this account.",
            },
        ) from error
    except SessionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "SESSION_NOT_FOUND",
                "message": "The attendance session was not found.",
            },
        ) from error

    return StudentAttendanceStateResponse.from_domain(state)
