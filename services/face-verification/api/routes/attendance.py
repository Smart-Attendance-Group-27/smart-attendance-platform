from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from api.dependencies.attendance import (
    get_attendance_face_verification_service,
)
from api.dependencies.auth import get_current_student_id
from api.dependencies.runtime import get_face_verification_settings
from api.face_image_upload import read_face_image_upload
from api.schemas.attendance import (
    AttendanceFaceVerificationResponse,
    LivenessFailureResponse,
)
from core.config import Settings
from services.attendance_face_verification_service import (
    AttendanceFaceVerificationService,
    AttendanceFaceVerificationBusyError,
    AttendanceFaceVerificationUnavailableError,
    VerificationClosedError,
    VerificationNotStartedError,
)
from services.liveness_evidence import (
    LivenessEvidenceValidationError,
    validate_liveness_evidence,
)


router = APIRouter(
    prefix="/internal/v1/attendance-sessions/{session_id}/face-verifications",
    tags=["attendance-face-verification"],
)


@router.post(
    "",
    response_model=AttendanceFaceVerificationResponse,
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": LivenessFailureResponse,
        }
    },
)
async def verify_attendance_face(
    session_id: UUID,
    image: Annotated[UploadFile, File(description="JPEG or PNG face capture")],
    student_id: Annotated[UUID, Depends(get_current_student_id)],
    service: Annotated[
        AttendanceFaceVerificationService,
        Depends(get_attendance_face_verification_service),
    ],
    settings: Annotated[Settings, Depends(get_face_verification_settings)],
    liveness: Annotated[
        str | None,
        Form(description="Optional serialized liveness evidence"),
    ] = None,
) -> AttendanceFaceVerificationResponse | JSONResponse:
    try:
        liveness_evidence = validate_liveness_evidence(
            liveness,
            max_age_seconds=settings.liveness_max_age_seconds,
        )
    except LivenessEvidenceValidationError:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=LivenessFailureResponse().model_dump(),
        )

    captured_image = await read_face_image_upload(image)

    try:
        result = await service.verify(
            session_id=session_id,
            student_id=student_id,
            captured_image=captured_image,
            liveness_evidence=liveness_evidence,
        )
    except VerificationNotStartedError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except VerificationClosedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except AttendanceFaceVerificationUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except AttendanceFaceVerificationBusyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    return AttendanceFaceVerificationResponse(
        status=result.status,
        attempt_number=result.attempt_number,
        can_retry=result.can_retry,
    )


__all__ = ["router"]
