from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from core.config import Settings, get_settings
from modules.attendance_verification.geofence.exception import (
    ActiveStudentProfileNotFoundError,
    AttendanceSessionNotActiveError,
    AttendanceSessionNotFoundError,
    CheckInClosedError,
    CheckInNotOpenError,
    GeofenceAttemptLimitReachedError,
    GeofenceNotConfiguredError,
    GeofenceNotRequiredError,
    GeofenceServiceError,
    StudentNotEligibleError,
    VerificationAttemptClosedError,
)
from modules.attendance_verification.geofence.policy import GeofenceValidationPolicy
from modules.attendance_verification.geofence.schemas import (
    CreateGeofenceAttemptRequest,
    CreateGeofenceAttemptResponse,
)
from modules.attendance_verification.geofence.service import (
    GeofenceValidationService,
)
from modules.attendance_verification.geofence.types import GeofenceReading
from modules.identity.auth.dependencies import CurrentStudent

router = APIRouter(
    prefix="/attendance-sessions/{session_id}/geofence-attempts",
    tags=["geofence-attempts"],
)


def get_geofence_validation_service(request: Request) -> GeofenceValidationService:
    settings = getattr(request.app.state, "settings", None)
    if not isinstance(settings, Settings):
        settings = get_settings()

    return GeofenceValidationService(
        policy=GeofenceValidationPolicy(
            max_reading_age_seconds=settings.geofence_max_reading_age_seconds,
            max_future_skew_seconds=settings.geofence_max_future_skew_seconds,
        ),
        max_attempts=settings.geofence_max_attempts,
    )


@router.post(
    "",
    response_model=CreateGeofenceAttemptResponse,
    status_code=status.HTTP_200_OK,
)
async def create_geofence_attempt(
    session_id: UUID,
    payload: CreateGeofenceAttemptRequest,
    http_request: Request,
    current_student: CurrentStudent,
    geofence_service: Annotated[
        GeofenceValidationService,
        Depends(get_geofence_validation_service),
    ] = None,  # type: ignore[assignment]
) -> CreateGeofenceAttemptResponse:
    try:
        recorded_attempt = await geofence_service.validate_attempt(
            http_request.app.state.db_pool,
            current_student.user_id,
            session_id,
            GeofenceReading(
                latitude=payload.latitude,
                longitude=payload.longitude,
                accuracy_m=payload.accuracy_m,
                captured_at=payload.captured_at,
                mocked=payload.mocked,
            ),
        )
    except ActiveStudentProfileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error.message,
        ) from error
    except AttendanceSessionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error.message,
        ) from error
    except StudentNotEligibleError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_error_detail(error),
        ) from error
    except (
        AttendanceSessionNotActiveError,
        CheckInNotOpenError,
        CheckInClosedError,
        GeofenceNotRequiredError,
        GeofenceNotConfiguredError,
        GeofenceAttemptLimitReachedError,
        VerificationAttemptClosedError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_error_detail(error),
        ) from error

    return CreateGeofenceAttemptResponse(
        verification_attempt_id=recorded_attempt.verification_attempt_id,
        attempt_number=recorded_attempt.attempt_number,
        decision=recorded_attempt.result.decision,
        distance_m=recorded_attempt.result.distance_m,
        allowed_radius_m=recorded_attempt.result.allowed_radius_m,
        next_step=recorded_attempt.result.next_step,
        reason=recorded_attempt.result.reason,
    )


def _error_detail(error: GeofenceServiceError) -> str:
    if error.reason is not None:
        return error.reason.value
    return error.message
