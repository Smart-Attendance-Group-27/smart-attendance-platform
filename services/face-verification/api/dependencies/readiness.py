from collections.abc import AsyncIterator

from fastapi import HTTPException, Request, status

from db.session import session_scope
from services.readiness_verification_service import ReadinessVerificationService


async def get_readiness_verification_service(request: Request,) -> AsyncIterator[ReadinessVerificationService]:

    session_factory = getattr(request.app.state,"db_session_factory",None,)

    face_engine = getattr(request.app.state, "face_engine", None)

    if session_factory is None or face_engine is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,detail="Face verification is unavailable",)

    async with session_scope(session_factory) as session:
        yield ReadinessVerificationService(session=session,face_engine=face_engine,)


__all__ = ["get_readiness_verification_service"]
