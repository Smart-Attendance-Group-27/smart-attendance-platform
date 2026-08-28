from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from core.config import Settings, get_settings
from modules.attendance_verification.face.client import (
    FaceVerificationServiceClient,
    FaceVerificationServiceError,
    FaceVerificationServiceRejectedError,
    InternalFaceVerificationResult,
)
from modules.attendance_verification.face.schemas import (
    AttendanceFaceVerificationResponse,
    PublicFaceStatus,
)
from modules.identity.auth.dependencies import CurrentStudent


MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = frozenset({"image/jpeg", "image/png"})

router = APIRouter(
    prefix="/attendance-sessions/{session_id}/face-verifications",
    tags=["attendance-face-verification"],
)


def get_face_verification_service_client(
    request: Request,
) -> FaceVerificationServiceClient:
    settings = getattr(request.app.state, "settings", None)
    if not isinstance(settings, Settings):
        settings = get_settings()
    if settings.face_verification_service_url is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Face verification is unavailable.",
        )

    return FaceVerificationServiceClient(
        base_url=settings.face_verification_service_url,
        timeout_seconds=settings.face_verification_timeout_seconds,
    )


@router.post("", response_model=AttendanceFaceVerificationResponse)
async def verify_attendance_face(
    session_id: UUID,
    image: Annotated[UploadFile, File(description="JPEG or PNG face capture")],
    request: Request,
    _current_student: CurrentStudent,
    client: Annotated[
        FaceVerificationServiceClient,
        Depends(get_face_verification_service_client),
    ],
) -> AttendanceFaceVerificationResponse:
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only JPEG and PNG images are supported",
        )

    try:
        captured_image = await image.read(MAX_IMAGE_BYTES + 1)
    finally:
        await image.close()

    if not captured_image:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded image is empty",
        )
    if len(captured_image) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="The uploaded image is too large",
        )

    authorization = request.headers.get("authorization", "")
    _, _, access_token = authorization.partition(" ")

    try:
        result = await client.verify_attendance_face(
            session_id=session_id,
            access_token=access_token,
            image=captured_image,
            content_type=image.content_type or "image/jpeg",
        )
    except FaceVerificationServiceRejectedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except FaceVerificationServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    return AttendanceFaceVerificationResponse(
        status=_public_status(result),
        attempt_number=result.attempt_number,
        can_retry=result.can_retry,
    )


def _public_status(result: InternalFaceVerificationResult) -> PublicFaceStatus:
    if result.status == "passed":
        return "success"
    if result.status == "no_face":
        return "face_not_detected"
    if result.status == "multiple_faces":
        return "multiple_faces"
    return "verification_failure"


__all__ = ["router"]
