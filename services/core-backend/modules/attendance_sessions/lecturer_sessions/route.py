from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.attendance_sessions.lecturer_sessions.exception import (
    ClassroomGeofenceNotConfiguredError,
    InvalidSessionScheduleError,
    SessionAlreadyActiveError,
    SessionAlreadyClosedError,
    SessionCancelledError,
    SessionNotActiveError,
    SessionNotFoundError,
    TimetableEntryNotFoundError,
)
from modules.attendance_sessions.lecturer_sessions.schemas import (
    CreateSessionRequest,
    LecturerSessionResponse,
    SessionStudentResponse,
)
from modules.attendance_sessions.lecturer_sessions.service import LecturerSessionService
from modules.identity.auth.dependencies import CurrentLecturer

router = APIRouter(prefix="/lecturers/me/attendance-sessions", tags=["lecturer-sessions"])

_PROFILE_NOT_FOUND_DETAIL = "An active lecturer profile was not found for this account."
_SESSION_NOT_FOUND_DETAIL = "The attendance session was not found."


def get_lecturer_session_service() -> LecturerSessionService:
    return LecturerSessionService()


@router.get("", response_model=list[LecturerSessionResponse], status_code=status.HTTP_200_OK)
async def list_my_attendance_sessions(
    http_request: Request,
    current_lecturer: CurrentLecturer,
    session_service: Annotated[
        LecturerSessionService,
        Depends(get_lecturer_session_service),
    ] = None,  # type: ignore[assignment]
) -> list[LecturerSessionResponse]:
    try:
        sessions = await session_service.list_for_user(
            http_request.app.state.db_pool,
            current_lecturer.user_id,
        )
    except LecturerProfileNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _PROFILE_NOT_FOUND_DETAIL) from error

    return [LecturerSessionResponse.from_record(session) for session in sessions]


@router.get(
    "/{session_id}",
    response_model=LecturerSessionResponse,
    status_code=status.HTTP_200_OK,
)
async def get_my_attendance_session(
    session_id: UUID,
    http_request: Request,
    current_lecturer: CurrentLecturer,
    session_service: Annotated[
        LecturerSessionService,
        Depends(get_lecturer_session_service),
    ] = None,  # type: ignore[assignment]
) -> LecturerSessionResponse:
    try:
        session = await session_service.get_for_user(
            http_request.app.state.db_pool,
            current_lecturer.user_id,
            session_id,
        )
    except LecturerProfileNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _PROFILE_NOT_FOUND_DETAIL) from error
    except SessionNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _SESSION_NOT_FOUND_DETAIL) from error

    return LecturerSessionResponse.from_record(session)


@router.post(
    "",
    response_model=LecturerSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_my_attendance_session(
    body: CreateSessionRequest,
    http_request: Request,
    current_lecturer: CurrentLecturer,
    session_service: Annotated[
        LecturerSessionService,
        Depends(get_lecturer_session_service),
    ] = None,  # type: ignore[assignment]
) -> LecturerSessionResponse:
    try:
        session = await session_service.create_for_user(
            http_request.app.state.db_pool,
            current_lecturer.user_id,
            timetable_entry_id=body.timetable_entry_id,
            session_title=body.session_title,
            session_type=body.session_type,
            scheduled_start_at=body.scheduled_start_at,
            scheduled_end_at=body.scheduled_end_at,
            check_in_opens_at=body.check_in_opens_at,
            check_in_closes_at=body.check_in_closes_at,
            late_after_at=body.late_after_at,
            requires_face_verification=body.requires_face_verification,
            requires_geofence=body.requires_geofence,
            requires_qr=body.requires_qr,
        )
    except LecturerProfileNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _PROFILE_NOT_FOUND_DETAIL) from error
    except TimetableEntryNotFoundError as error:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "The timetable entry was not found for this lecturer.",
        ) from error
    except InvalidSessionScheduleError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    except ClassroomGeofenceNotConfiguredError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error

    return LecturerSessionResponse.from_record(session)


@router.post(
    "/{session_id}/activate",
    response_model=LecturerSessionResponse,
    status_code=status.HTTP_200_OK,
)
async def activate_my_attendance_session(
    session_id: UUID,
    http_request: Request,
    current_lecturer: CurrentLecturer,
    session_service: Annotated[
        LecturerSessionService,
        Depends(get_lecturer_session_service),
    ] = None,  # type: ignore[assignment]
) -> LecturerSessionResponse:
    try:
        session = await session_service.activate_for_user(
            http_request.app.state.db_pool,
            current_lecturer.user_id,
            session_id,
        )
    except LecturerProfileNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _PROFILE_NOT_FOUND_DETAIL) from error
    except SessionNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _SESSION_NOT_FOUND_DETAIL) from error
    except (SessionAlreadyActiveError, SessionAlreadyClosedError, SessionCancelledError) as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This session cannot be activated in its current state.",
        ) from error

    return LecturerSessionResponse.from_record(session)


@router.post(
    "/{session_id}/close",
    response_model=LecturerSessionResponse,
    status_code=status.HTTP_200_OK,
)
async def close_my_attendance_session(
    session_id: UUID,
    http_request: Request,
    current_lecturer: CurrentLecturer,
    session_service: Annotated[
        LecturerSessionService,
        Depends(get_lecturer_session_service),
    ] = None,  # type: ignore[assignment]
) -> LecturerSessionResponse:
    try:
        session = await session_service.close_for_user(
            http_request.app.state.db_pool,
            current_lecturer.user_id,
            session_id,
        )
    except LecturerProfileNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _PROFILE_NOT_FOUND_DETAIL) from error
    except SessionNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _SESSION_NOT_FOUND_DETAIL) from error
    except (SessionNotActiveError, SessionAlreadyClosedError, SessionCancelledError) as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This session cannot be closed in its current state.",
        ) from error

    return LecturerSessionResponse.from_record(session)


@router.get(
    "/{session_id}/students",
    response_model=list[SessionStudentResponse],
    status_code=status.HTTP_200_OK,
)
async def list_my_attendance_session_students(
    session_id: UUID,
    http_request: Request,
    current_lecturer: CurrentLecturer,
    session_service: Annotated[
        LecturerSessionService,
        Depends(get_lecturer_session_service),
    ] = None,  # type: ignore[assignment]
) -> list[SessionStudentResponse]:
    try:
        students = await session_service.list_students_for_user(
            http_request.app.state.db_pool,
            current_lecturer.user_id,
            session_id,
        )
    except LecturerProfileNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _PROFILE_NOT_FOUND_DETAIL) from error
    except SessionNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _SESSION_NOT_FOUND_DETAIL) from error

    return [
        SessionStudentResponse(
            student_id=student.student_id,
            registration_number=student.registration_number or "",
            full_name=student.full_name,
            verification_status=student.verification_status,
            geofence_status=student.geofence_status,
            face_status=student.face_status,
            face_similarity_score=(
                float(student.face_similarity_score)
                if student.face_similarity_score is not None
                else None
            ),
            face_liveness_passed=student.face_liveness_passed,
            qr_status=student.qr_status,
            attendance_status=student.attendance_status,
            review_status=student.review_status,
            checked_in_at=student.checked_in_at,
        )
        for student in students
    ]
