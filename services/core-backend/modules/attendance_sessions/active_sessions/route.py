from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from modules.academic.student_profile.exception import StudentProfileNotFoundError
from modules.attendance_sessions.active_sessions.schemas import (
    ActiveAttendanceSessionResponse,
)
from modules.attendance_sessions.active_sessions.service import (
    ActiveAttendanceSessionService,
)
from modules.identity.auth.dependencies import CurrentStudent

router = APIRouter(
    prefix="/students/me/attendance-sessions",
    tags=["attendance-sessions"],
)


def get_active_attendance_session_service() -> ActiveAttendanceSessionService:
    return ActiveAttendanceSessionService()


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
            detail="An active student profile was not found for this account.",
        ) from error

    return [
        ActiveAttendanceSessionResponse(
            id=session.id,
            course_code=session.course_code or "",
            course_name=session.course_name or "",
            session_title=session.session_title or "",
            session_type=session.session_type or "",
            scheduled_start_at=session.scheduled_start_at,
            scheduled_end_at=session.scheduled_end_at,
            check_in_opens_at=session.check_in_opens_at,
            check_in_closes_at=session.check_in_closes_at,
            late_after_at=session.late_after_at,
            venue=session.venue,
            requires_face_verification=session.requires_face_verification,
            requires_geofence=session.requires_geofence,
            requires_qr=session.requires_qr,
        )
        for session in sessions
    ]
