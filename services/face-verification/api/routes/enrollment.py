import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from api.dependencies.admin import get_current_administrator_id
from api.dependencies.runtime import get_face_verification_runtime
from api.schemas.enrollment import ReferenceFaceEnrollmentResponse
from db.session import AsyncSessionFactory
from scripts.enroll_reference_faces import import_reference_photos
from services.face_engine import FaceEngine


router = APIRouter(
    prefix="/internal/v1/reference-faces",
    tags=["reference-face-enrollment"],
)
MAX_ENROLLMENT_IMAGES = 500
MAX_ENROLLMENT_IMAGE_BYTES = 5 * 1024 * 1024
MAX_ENROLLMENT_BATCH_BYTES = 250 * 1024 * 1024
ALLOWED_IMAGE_CONTENT_TYPES = frozenset(
    {"image/jpeg", "image/png", "application/octet-stream"}
)
ALLOWED_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png"})


@router.post(
    "/enrolments/upload",
    response_model=ReferenceFaceEnrollmentResponse,
    status_code=status.HTTP_200_OK,
)
async def enroll_uploaded_reference_faces(
    request: Request,
    administrator_id: Annotated[UUID, Depends(get_current_administrator_id)],
    images: Annotated[
        list[UploadFile],
        File(description="Student JPEG or PNG photographs"),
    ],
) -> ReferenceFaceEnrollmentResponse:
    del administrator_id
    if not images or len(images) > MAX_ENROLLMENT_IMAGES:
        await _close_uploads(images)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Select between 1 and {MAX_ENROLLMENT_IMAGES} images.",
        )

    runtime = get_face_verification_runtime(request)
    lock = getattr(request.app.state, "reference_enrollment_lock", None)
    if not isinstance(lock, asyncio.Lock):
        await _close_uploads(images)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Reference-face enrolment is unavailable.",
        )
    if lock.locked():
        await _close_uploads(images)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another reference-face enrolment is already running.",
        )

    try:
        async with lock:
            with TemporaryDirectory(prefix="uniattend-face-enrolment-") as temp_directory:
                photos_directory = Path(temp_directory)
                await stage_enrollment_uploads(images, photos_directory)
                summary = await import_reference_photos(
                    photos_directory=photos_directory,
                    commit=True,
                    settings=runtime.settings,
                    session_factory=cast(
                        AsyncSessionFactory, request.app.state.db_session_factory
                    ),
                    face_engine=cast(FaceEngine, request.app.state.face_engine),
                    report=lambda message: None,
                )
    finally:
        await _close_uploads(images)

    return ReferenceFaceEnrollmentResponse(
        discovered=summary.discovered,
        enrolled=summary.enrolled,
        already_enrolled=summary.already_enrolled,
        skipped=summary.skipped,
        failed=summary.failed,
    )


async def stage_enrollment_uploads(images: list[UploadFile], destination: Path) -> None:
    seen_names: set[str] = set()
    total_bytes = 0
    for image in images:
        filename = (image.filename or "").strip()
        if (
            not filename
            or "/" in filename
            or "\\" in filename
            or Path(filename).name != filename
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Every image must have a safe filename.",
            )

        normalized_name = filename.casefold()
        if normalized_name in seen_names:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image filenames must be unique.",
            )
        seen_names.add(normalized_name)

        if (
            Path(filename).suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS
            or image.content_type not in ALLOWED_IMAGE_CONTENT_TYPES
        ):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Only JPEG and PNG images are supported.",
            )

        photo_bytes = await image.read(MAX_ENROLLMENT_IMAGE_BYTES + 1)
        if not photo_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{filename} is empty.",
            )
        if len(photo_bytes) > MAX_ENROLLMENT_IMAGE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"{filename} exceeds the 5 MB image limit.",
            )
        total_bytes += len(photo_bytes)
        if total_bytes > MAX_ENROLLMENT_BATCH_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="The selected image batch exceeds the 250 MB limit.",
            )
        await asyncio.to_thread((destination / filename).write_bytes, photo_bytes)


async def _close_uploads(images: list[UploadFile]) -> None:
    await asyncio.gather(*(image.close() for image in images), return_exceptions=True)


__all__ = ["router", "stage_enrollment_uploads"]
