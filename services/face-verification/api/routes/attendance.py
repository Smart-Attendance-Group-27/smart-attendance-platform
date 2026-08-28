from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from api.dependencies.attendance import (
    get_attendance_face_verification_service,
)
from api.dependencies.auth import get_current_student_id
from api.face_image_upload import read_face_image_upload
from api.schemas.attendance import AttendanceFaceVerificationResponse
from services.attendance_face_verification_service import (
    AttendanceFaceVerificationService,
    AttendanceFaceVerificationUnavailableError,
    VerificationClosedError,
    VerificationNotStartedError,
)


router = APIRouter(
    prefix="/internal/v1/attendance-sessions/{session_id}/face-verifications",
    tags=["attendance-face-verification"],
)


@router.post("", response_model=AttendanceFaceVerificationResponse)
async def verify_attendance_face(
    session_id: UUID,
    image: Annotated[UploadFile, File(description="JPEG or PNG face capture")],
    student_id: Annotated[UUID, Depends(get_current_student_id)],
    service: Annotated[
        AttendanceFaceVerificationService,
        Depends(get_attendance_face_verification_service),
    ],
) -> AttendanceFaceVerificationResponse:
    captured_image = await read_face_image_upload(image)

    try:
        result = await service.verify(
            session_id=session_id,
            student_id=student_id,
            captured_image=captured_image,
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

    return AttendanceFaceVerificationResponse(
        status=result.status,
        attempt_number=result.attempt_number,
        can_retry=result.can_retry,
    )


__all__ = ["router"]
