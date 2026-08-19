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

from api.dependencies.auth import get_current_student_id
from api.dependencies.readiness import get_readiness_verification_service
from api.schemas.readiness import (
    ReadinessStatusResponse,
    ReadinessVerificationResponse,
)
from services.readiness_verification_service import (
    ReadinessVerificationService,
    ReadinessVerificationResult,
    ReadinessVerificationStatus,
)


MAX_IMAGE_BYTES = 5 * 1024 * 1024
logger = logging.getLogger("uvicorn.error")

# type cannot be changed after it is created
ALLOWED_IMAGE_TYPES = frozenset({"image/jpeg", "image/png"})

router = APIRouter(prefix="/api/v1/face-verification",tags=["face-verification"],)


@router.get(
    "/readiness/status",
    response_model=ReadinessStatusResponse,
)
async def get_readiness_status(
    student_id: Annotated[UUID, Depends(get_current_student_id)],
    service: Annotated[
        ReadinessVerificationService,
        Depends(get_readiness_verification_service),
    ],
) -> ReadinessStatusResponse:
    result = await service.get_status(student_id=student_id)

    return ReadinessStatusResponse(
        status=result.status,
        requires_readiness_check=result.requires_readiness_check,
        checked_at=result.checked_at,
    )


@router.post("/readiness",response_model=ReadinessVerificationResponse,)

async def verify_readiness(
    request: Request,
    image: Annotated[UploadFile, File(description="JPEG or PNG face capture")],
    student_id: Annotated[UUID, Depends(get_current_student_id)],
    service: Annotated[ReadinessVerificationService,Depends(get_readiness_verification_service),],
) -> ReadinessVerificationResponse:
    
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,detail="Only JPEG and PNG images are supported",)

    try:
        captured_image = await image.read(MAX_IMAGE_BYTES + 1)

    finally:
        await image.close()

    if not captured_image:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="The uploaded image is empty",)

    if len(captured_image) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE,detail="The uploaded image is too large",)

    result = await service.verify(
        student_id=student_id,
        captured_image=captured_image,
    )

    if _development_diagnostics_enabled(request):
        _log_readiness_diagnostics(result)

    return ReadinessVerificationResponse(
        status=result.status,
        message=_message_for_status(result.status),
    )


def _development_diagnostics_enabled(request: Request) -> bool:
    settings = getattr(request.app.state, "settings", None)
    environment = getattr(settings, "app_environment", "")

    return (
        isinstance(environment, str)
        and environment.strip().lower() == "development"
    )


def _log_readiness_diagnostics(result: ReadinessVerificationResult) -> None:
    """Log comparison metadata without tokens, images, or embeddings."""

    logger.info(
        "Face readiness diagnostic: status=%s student_id=%s profile_id=%s "
        "verification_config_id=%s similarity_score=%s "
        "similarity_threshold=%s detection_confidence=%s model_name=%s "
        "failure_reason=%s",
        result.status.value,
        result.student_id,
        result.profile_id,
        result.verification_config_id,
        result.similarity_score,
        result.similarity_threshold,
        result.detection_confidence,
        result.model_name,
        result.failure_reason,
    )


def _message_for_status(status_value: ReadinessVerificationStatus) -> str:
    messages = {
        ReadinessVerificationStatus.PASSED: "Face readiness verification passed",
        ReadinessVerificationStatus.FAILED: "Face readiness verification failed",
        ReadinessVerificationStatus.PROFILE_NOT_ENROLLED: "A reference face profile is not available",
        ReadinessVerificationStatus.NO_ACTIVE_CONFIG: "Face readiness verification is unavailable",
        ReadinessVerificationStatus.NO_FACE: "No face was detected",
        ReadinessVerificationStatus.MULTIPLE_FACES: "More than one face was detected",
        ReadinessVerificationStatus.LOW_QUALITY: "The captured image quality is too low",
        ReadinessVerificationStatus.PROCESSING_FAILED: "The captured image could not be processed",
        ReadinessVerificationStatus.MODEL_MISMATCH:"Face readiness verification is unavailable",
    }

    return messages[status_value]


__all__ = ["router"]
