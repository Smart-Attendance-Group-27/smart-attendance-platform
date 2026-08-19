from collections.abc import AsyncIterator

from fastapi import HTTPException, Request, status

from db.session import session_scope
from services.attendance_face_verification_service import (
    AttendanceFaceVerificationService,
)
from services.face_comparison_service import FaceComparisonService


async def get_attendance_face_verification_service(
    request: Request,
) -> AsyncIterator[AttendanceFaceVerificationService]:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    face_engine = getattr(request.app.state, "face_engine", None)
    settings = getattr(request.app.state, "settings", None)

    if session_factory is None or face_engine is None or settings is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Face verification is unavailable",
        )

    async with session_scope(session_factory) as session:
        yield AttendanceFaceVerificationService(
            session=session,
            face_comparison_service=FaceComparisonService(
                face_engine=face_engine,
                model_version=settings.face_model_version,
            ),
        )


__all__ = ["get_attendance_face_verification_service"]
