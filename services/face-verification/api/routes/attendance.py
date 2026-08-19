import logging
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)

from api.dependencies.attendance import get_attendance_face_verification_service
from api.dependencies.auth import get_current_student_id
from api.schemas.attendance import AttendanceFaceVerificationResponse
from services.attendance_face_verification_service import (
    AttendanceFaceVerificationResult,
    AttendanceFaceVerificationService,
    AttendanceFaceVerificationStatus,
)

MAX_IMAGE_BYTES = 5 * 1024 * 1024
logger = logging.getLogger("uvicorn.error")

ALLOWED_IMAGE_TYPES = frozenset({"image/jpeg", "image/png"})

router = APIRouter(prefix="/api/v1/face-verification", tags=["face-verification"])


@router.post(
    "/attendance-sessions/{session_id}/verify",
    response_model=AttendanceFaceVerificationResponse,
)
async def verify_attendance_face(
    session_id: UUID,
    request: Request,
    image: Annotated[UploadFile, File(description="JPEG or PNG face capture")],
    student_id: Annotated[UUID, Depends(get_current_student_id)],
    service: Annotated[
        AttendanceFaceVerificationService,
        Depends(get_attendance_face_verification_service),
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded image is empty")

    if len(captured_image) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="The uploaded image is too large")

    result = await service.verify(
        session_id=session_id,
        student_id=student_id,
        captured_image=captured_image,
    )

    if _development_diagnostics_enabled(request):
        _log_attendance_diagnostics(session_id, result)

    return AttendanceFaceVerificationResponse(
        status=result.status,
        message=_message_for_status(result.status),
        similarity_score=result.similarity_score,
    )


def _development_diagnostics_enabled(request: Request) -> bool:
    settings = getattr(request.app.state, "settings", None)
    environment = getattr(settings, "app_environment", "")
    return isinstance(environment, str) and environment.strip().lower() == "development"


def _log_attendance_diagnostics(
    session_id: UUID,
    result: AttendanceFaceVerificationResult,
) -> None:
    """Log comparison metadata without tokens, images, or embeddings."""
    logger.info(
        "Attendance face verification diagnostic: session_id=%s status=%s "
        "student_id=%s verification_attempt_id=%s attempt_number=%s "
        "similarity_score=%s similarity_threshold=%s failure_reason=%s",
        session_id,
        result.status.value,
        result.student_id,
        result.verification_attempt_id,
        result.attempt_number,
        result.similarity_score,
        result.similarity_threshold,
        result.failure_reason,
    )


def _message_for_status(status_value: AttendanceFaceVerificationStatus) -> str:
    messages = {
        AttendanceFaceVerificationStatus.PASSED: "Face verification passed",
        AttendanceFaceVerificationStatus.FAILED: "Face verification failed",
        AttendanceFaceVerificationStatus.VERIFICATION_ATTEMPT_NOT_FOUND: (
            "No verification attempt was found for this session — complete the geofence check first"
        ),
        AttendanceFaceVerificationStatus.VERIFICATION_ATTEMPT_CLOSED: (
            "This session's verification attempt is already complete"
        ),
        AttendanceFaceVerificationStatus.PROFILE_NOT_ENROLLED: "A reference face profile is not available",
        AttendanceFaceVerificationStatus.NO_ACTIVE_CONFIG: "Face verification is unavailable",
        AttendanceFaceVerificationStatus.NO_FACE: "No face was detected",
        AttendanceFaceVerificationStatus.MULTIPLE_FACES: "More than one face was detected",
        AttendanceFaceVerificationStatus.LOW_QUALITY: "The captured image quality is too low",
        AttendanceFaceVerificationStatus.PROCESSING_FAILED: "The captured image could not be processed",
        AttendanceFaceVerificationStatus.MODEL_MISMATCH: "Face verification is unavailable",
    }
    return messages[status_value]


__all__ = ["router"]
