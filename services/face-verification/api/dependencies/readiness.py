from collections.abc import AsyncIterator

from fastapi import Request

from api.dependencies.runtime import get_face_verification_runtime
from db.session import session_scope
from services.readiness_verification_service import ReadinessVerificationService


async def get_readiness_verification_service(request: Request,) -> AsyncIterator[ReadinessVerificationService]:
    runtime = get_face_verification_runtime(request)

    # session remains available while the request is processed
    # and is automatically cleaned up afterward
    async with session_scope(runtime.session_factory) as session:
        yield ReadinessVerificationService(
            session=session,
            face_comparison_service=runtime.comparison_service,
        )


__all__ = ["get_readiness_verification_service"]
