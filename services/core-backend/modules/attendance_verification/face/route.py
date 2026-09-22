import logging
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)

from core.config import Settings, get_settings
from core.errors import error_detail
from modules.attendance_verification.check_in.exception import CheckInServiceError
from modules.attendance_verification.check_in.route import get_check_in_service
from modules.attendance_verification.check_in.schemas import InitialCheckInPayload
from modules.attendance_verification.check_in.service import CheckInService
from modules.attendance_verification.face.client import (
    FaceVerificationServiceClient,
    FaceVerificationServiceError,
    FaceVerificationServiceInvalidRequestError,
    FaceVerificationServiceRejectedError,
    InternalFaceVerificationResult,
)
from modules.attendance_verification.face.schemas import (
    AttendanceFaceProgressResponse,
    AttendanceFaceVerificationResponse,
    PublicFaceStatus,
)
from modules.attendance_verification.face.repository import (
    AttendanceFaceProgressRepository,
)
from modules.identity.auth.dependencies import CurrentStudent


logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_LIVENESS_CHARS = 4096
ALLOWED_IMAGE_TYPES = frozenset({"image/jpeg", "image/png"})

router = APIRouter(
    prefix="/attendance-sessions/{session_id}/face-verifications",
    tags=["attendance-face-verification"],
)


def get_face_progress_repository() -> AttendanceFaceProgressRepository:
    return AttendanceFaceProgressRepository()


@router.get("", response_model=AttendanceFaceProgressResponse)
async def get_attendance_face_progress(
    session_id: UUID,
    request: Request,
    current_student: CurrentStudent,
    repository: Annotated[
        AttendanceFaceProgressRepository,
        Depends(get_face_progress_repository),
    ],
) -> AttendanceFaceProgressResponse:
    passed = await repository.has_passed(
        request.app.state.db_pool,
        user_id=current_student.user_id,
        session_id=session_id,
    )
    return AttendanceFaceProgressResponse(
        status="passed" if passed else "required"
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
            detail=error_detail(
                "FACE_VERIFICATION_UNAVAILABLE", "Face verification is unavailable.",
            ),
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
    current_student: CurrentStudent,
    client: Annotated[
        FaceVerificationServiceClient,
        Depends(get_face_verification_service_client),
    ],
    check_in_service: Annotated[
        CheckInService,
        Depends(get_check_in_service),
    ],
    liveness: Annotated[
        str | None,
        Form(description="On-device liveness evidence, passed through as-is"),
    ] = None,
) -> AttendanceFaceVerificationResponse:
    if liveness is not None and len(liveness) > MAX_LIVENESS_CHARS:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="The liveness evidence is too large",
        )

    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=error_detail(
                "UNSUPPORTED_IMAGE_TYPE", "Only JPEG and PNG images are supported",
            ),
        )

    try:
        captured_image = await image.read(MAX_IMAGE_BYTES + 1)
    finally:
        await image.close()

    if not captured_image:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail("EMPTY_IMAGE", "The uploaded image is empty"),
        )
    if len(captured_image) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=error_detail("IMAGE_TOO_LARGE", "The uploaded image is too large"),
        )

    authorization = request.headers.get("authorization", "")
    _, _, access_token = authorization.partition(" ")

    try:
        result = await client.verify_attendance_face(
            session_id=session_id,
            access_token=access_token,
            image=captured_image,
            content_type=image.content_type or "image/jpeg",
            liveness=liveness,
        )
    except FaceVerificationServiceRejectedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_detail("FACE_VERIFICATION_REJECTED", str(error)),
        ) from error
    except FaceVerificationServiceInvalidRequestError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=error_detail("FACE_VERIFICATION_INVALID_REQUEST", str(error)),
        ) from error
    except FaceVerificationServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("FACE_VERIFICATION_SERVICE_ERROR", str(error)),
        ) from error

    initial_check_in = None
    if result.status == "passed":
        initial_check_in = await _check_in_after_pass(
            check_in_service,
            request,
            user_id=current_student.user_id,
            session_id=session_id,
        )

    return AttendanceFaceVerificationResponse(
        status=_public_status(result),
        attempt_number=result.attempt_number,
        can_retry=result.can_retry,
        initial_check_in=initial_check_in,
    )


async def _check_in_after_pass(
    check_in_service: CheckInService,
    request: Request,
    *,
    user_id: UUID,
    session_id: UUID,
) -> InitialCheckInPayload | None:
    """Check the student in after a face pass. Runs in its own transaction."""

    try:
        result = await check_in_service.check_in_for_user(
            request.app.state.db_pool,
            user_id,
            session_id,
        )
    except CheckInServiceError:
        logger.warning(
            "Face verification passed but check-in did not complete for session %s",
            session_id,
        )
        return None

    if result.initial_check_in is None:
        return None
    return InitialCheckInPayload.from_domain(result.initial_check_in)


def _public_status(result: InternalFaceVerificationResult) -> PublicFaceStatus:
    if result.status == "passed":
        return "success"
    if result.status == "no_face":
        return "face_not_detected"
    if result.status == "multiple_faces":
        return "multiple_faces"
    return "verification_failure"


__all__ = ["router"]
