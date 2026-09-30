from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from core.config import Settings, get_settings
from core.errors import error_detail
from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.attendance_verification.session_overrides.exception import (
    GeofenceNotRequiredError,
    InvalidWaiverReasonError,
    SessionNotActiveError,
    SessionNotFoundError,
)
from modules.attendance_verification.session_overrides.schemas import (
    GeofenceWaiverRequest,
    GeofenceWaiverResponse,
    SessionVerificationPolicyResponse,
)
from modules.attendance_verification.session_overrides.service import SessionOverrideService
from modules.identity.auth.dependencies import CurrentLecturer

router = APIRouter(
    prefix="/lecturers/me/attendance-sessions/{session_id}",
    tags=["session-verification-overrides"],
)


def get_session_override_service(request: Request) -> SessionOverrideService:
    settings = getattr(request.app.state, "settings", None)
    if not isinstance(settings, Settings):
        settings = get_settings()
    return SessionOverrideService(
        warning_min_attempts=settings.geofence_health_warning_min_attempts,
        warning_failure_rate=settings.geofence_health_warning_failure_rate,
    )


def _not_found(error: Exception) -> HTTPException:
    if isinstance(error, LecturerProfileNotFoundError):
        return HTTPException(
            status.HTTP_404_NOT_FOUND,
            error_detail(
                "LECTURER_PROFILE_NOT_FOUND",
                "An active lecturer profile was not found for this account.",
            ),
        )
    return HTTPException(
        status.HTTP_404_NOT_FOUND,
        error_detail("SESSION_NOT_FOUND", "The attendance session was not found."),
    )


@router.get(
    "/verification-policy",
    response_model=SessionVerificationPolicyResponse,
    status_code=status.HTTP_200_OK,
)
async def get_session_verification_policy(
    session_id: UUID,
    http_request: Request,
    current_lecturer: CurrentLecturer,
    service: Annotated[SessionOverrideService, Depends(get_session_override_service)],
) -> SessionVerificationPolicyResponse:
    try:
        view = await service.get_policy_for_user(
            http_request.app.state.db_pool,
            current_lecturer.user_id,
            session_id,
        )
    except (LecturerProfileNotFoundError, SessionNotFoundError) as error:
        raise _not_found(error) from error

    return SessionVerificationPolicyResponse.from_view(view)


@router.post(
    "/verification-overrides/geofence",
    response_model=GeofenceWaiverResponse,
    status_code=status.HTTP_200_OK,
)
async def waive_session_geofence(
    session_id: UUID,
    body: GeofenceWaiverRequest,
    http_request: Request,
    current_lecturer: CurrentLecturer,
    service: Annotated[SessionOverrideService, Depends(get_session_override_service)],
) -> GeofenceWaiverResponse:
    """Waive geofence for the whole session. Safe to repeat: a second call
    returns the existing waiver with ``created`` false."""

    try:
        result = await service.waive_geofence_for_user(
            http_request.app.state.db_pool,
            current_lecturer.user_id,
            session_id,
            reason_code=body.reason_code.value,
            reason_text=body.reason_text,
        )
    except (LecturerProfileNotFoundError, SessionNotFoundError) as error:
        raise _not_found(error) from error
    except SessionNotActiveError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            error_detail("SESSION_NOT_ACTIVE", "Geofence can only be waived while the session is active."),
        ) from error
    except GeofenceNotRequiredError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            error_detail("GEOFENCE_NOT_REQUIRED", "This session does not require geofence verification."),
        ) from error
    except InvalidWaiverReasonError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            error_detail("REASON_INVALID", "A description is required when the reason is OTHER."),
        ) from error

    return GeofenceWaiverResponse.from_result(result)


__all__ = ["router"]
