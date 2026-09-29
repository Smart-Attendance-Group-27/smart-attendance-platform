import logging
from time import perf_counter
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from core.config import Settings, get_settings
from core.errors import error_detail
from modules.academic.admin_reference_faces.client import (
    ReferenceFaceEnrollmentBusyError,
    ReferenceFaceEnrollmentClient,
    ReferenceFaceEnrollmentClientError,
    ReferenceFaceEnrollmentUploadError,
    ReferenceFaceEnrollmentPhoto,
)
from modules.academic.admin_reference_faces.schemas import (
    ReferenceFaceEnrollmentResponse,
    ReferenceFaceResponse,
)
from modules.academic.admin_reference_faces.service import AdminReferenceFaceService
from modules.identity.auth.dependencies import CurrentAdministrator

router = APIRouter(prefix="/administrators/me", tags=["admin-reference-faces"])
MAX_ENROLLMENT_IMAGES = 500
logger = logging.getLogger("uvicorn.error")


def get_admin_reference_face_service(request: Request) -> AdminReferenceFaceService:
    settings = getattr(request.app.state, "settings", None)
    if not isinstance(settings, Settings):
        settings = get_settings()
    enrollment_client = None
    if settings.face_verification_service_url is not None:
        enrollment_client = ReferenceFaceEnrollmentClient(
            base_url=settings.face_verification_service_url,
            timeout_seconds=settings.face_enrollment_timeout_seconds,
        )
    return AdminReferenceFaceService(enrollment_client=enrollment_client)


@router.get(
    "/reference-faces",
    response_model=list[ReferenceFaceResponse],
    status_code=status.HTTP_200_OK,
)
async def list_reference_faces(
    http_request: Request,
    current_administrator: CurrentAdministrator,
    reference_face_service: Annotated[
        AdminReferenceFaceService,
        Depends(get_admin_reference_face_service),
    ] = None,  # type: ignore[assignment]
) -> list[ReferenceFaceResponse]:
    records = await reference_face_service.list_reference_faces(http_request.app.state.db_pool)
    return [ReferenceFaceResponse.from_record(record) for record in records]


@router.post(
    "/reference-faces/enrolments/upload",
    response_model=ReferenceFaceEnrollmentResponse,
    status_code=status.HTTP_200_OK,
)
async def enroll_uploaded_reference_faces(
    images: Annotated[list[UploadFile], File(description="Student JPEG or PNG photographs")],
    http_request: Request,
    current_administrator: CurrentAdministrator,
    reference_face_service: Annotated[
        AdminReferenceFaceService,
        Depends(get_admin_reference_face_service),
    ] = None,  # type: ignore[assignment]
) -> ReferenceFaceEnrollmentResponse:
    operation_id = uuid4()
    started_at = perf_counter()
    uploaded_bytes = sum(image.size or 0 for image in images)
    logger.info(
        "Reference-face enrolment started: operation_id=%s administrator_id=%s "
        "image_count=%s uploaded_bytes=%s",
        operation_id,
        current_administrator.user_id,
        len(images),
        uploaded_bytes,
    )

    if not images or len(images) > MAX_ENROLLMENT_IMAGES:
        logger.warning(
            "Reference-face enrolment rejected: operation_id=%s reason=invalid_image_count "
            "image_count=%s elapsed_seconds=%.3f",
            operation_id,
            len(images),
            perf_counter() - started_at,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail(
                "INVALID_ENROLLMENT_IMAGE_COUNT",
                f"Select between 1 and {MAX_ENROLLMENT_IMAGES} images.",
            ),
        )

    authorization = http_request.headers.get("authorization", "")
    _, _, access_token = authorization.partition(" ")
    photos = [
        ReferenceFaceEnrollmentPhoto(
            filename=image.filename or "",
            content_type=image.content_type or "application/octet-stream",
            file=image.file,
        )
        for image in images
    ]

    try:
        result = await reference_face_service.enroll_uploaded_reference_faces(
            photos=photos,
            access_token=access_token,
        )
    except ReferenceFaceEnrollmentUploadError as error:
        logger.warning(
            "Reference-face enrolment rejected: operation_id=%s reason=invalid_upload "
            "elapsed_seconds=%.3f",
            operation_id,
            perf_counter() - started_at,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail("INVALID_ENROLLMENT_UPLOAD", str(error)),
        ) from error
    except ReferenceFaceEnrollmentBusyError as error:
        logger.warning(
            "Reference-face enrolment rejected: operation_id=%s reason=batch_already_running "
            "elapsed_seconds=%.3f",
            operation_id,
            perf_counter() - started_at,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_detail("ENROLLMENT_ALREADY_RUNNING", str(error)),
        ) from error
    except (ReferenceFaceEnrollmentClientError, RuntimeError) as error:
        logger.error(
            "Reference-face enrolment failed: operation_id=%s reason=service_unavailable "
            "elapsed_seconds=%.3f error_type=%s",
            operation_id,
            perf_counter() - started_at,
            type(error).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail(
                "REFERENCE_FACE_ENROLLMENT_UNAVAILABLE",
                "Reference-face enrolment is unavailable.",
            ),
        ) from error
    finally:
        for image in images:
            await image.close()

    elapsed_seconds = perf_counter() - started_at
    logger.info(
        "Reference-face enrolment completed: operation_id=%s administrator_id=%s "
        "image_count=%s uploaded_bytes=%s discovered=%s enrolled=%s "
        "already_enrolled=%s skipped=%s failed=%s elapsed_seconds=%.3f",
        operation_id,
        current_administrator.user_id,
        len(images),
        uploaded_bytes,
        result.discovered,
        result.enrolled,
        result.already_enrolled,
        result.skipped,
        result.failed,
        elapsed_seconds,
    )
    return ReferenceFaceEnrollmentResponse.from_result(result)
