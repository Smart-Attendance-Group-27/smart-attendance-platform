from collections.abc import AsyncIterator

from fastapi import Request

from api.dependencies.runtime import get_face_verification_runtime
from db.session import session_scope
from services.attendance_face_verification_service import (
    AttendanceFaceVerificationService,
)


async def get_attendance_face_verification_service(
    request: Request,
) -> AsyncIterator[AttendanceFaceVerificationService]:
    runtime = get_face_verification_runtime(request)

    async with session_scope(runtime.session_factory) as session:
        yield AttendanceFaceVerificationService(
            session=session,
            face_comparison_service=runtime.comparison_service,
            max_attempts=runtime.settings.face_max_attempts,
        )


__all__ = ["get_attendance_face_verification_service"]
