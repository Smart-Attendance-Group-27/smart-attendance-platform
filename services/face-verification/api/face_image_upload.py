from fastapi import HTTPException, UploadFile, status


MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = frozenset({"image/jpeg", "image/png"})


async def read_face_image_upload(image: UploadFile) -> bytes:
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

    return captured_image


__all__ = [
    "ALLOWED_IMAGE_TYPES",
    "MAX_IMAGE_BYTES",
    "read_face_image_upload",
]
