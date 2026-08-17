from pydantic import BaseModel

from services.readiness_verification_service import (
    ReadinessVerificationStatus,
)


class ReadinessVerificationResponse(BaseModel):
    status: ReadinessVerificationStatus
    message: str