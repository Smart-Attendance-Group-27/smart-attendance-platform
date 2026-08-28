from dataclasses import dataclass
from typing import cast

from fastapi import HTTPException, Request, status

from core.config import Settings
from db.session import AsyncSessionFactory
from services.face_comparison_service import FaceComparisonService
from services.face_engine import FaceEngine


@dataclass(frozen=True, slots=True)
class FaceVerificationRuntime:
    session_factory: AsyncSessionFactory
    comparison_service: FaceComparisonService
    settings: Settings


def get_face_verification_runtime(request: Request) -> FaceVerificationRuntime:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    face_engine = getattr(request.app.state, "face_engine", None)
    settings = getattr(request.app.state, "settings", None)

    if (
        session_factory is None
        or face_engine is None
        or not isinstance(settings, Settings)
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Face verification is unavailable",
        )

    return FaceVerificationRuntime(
        session_factory=cast(AsyncSessionFactory, session_factory),
        comparison_service=FaceComparisonService(
            face_engine=cast(FaceEngine, face_engine),
            model_version=settings.face_model_version,
        ),
        settings=settings,
    )


__all__ = ["FaceVerificationRuntime", "get_face_verification_runtime"]
