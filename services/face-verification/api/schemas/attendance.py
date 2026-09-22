from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from services.attendance_face_verification_service import (
    AttendanceFaceVerificationStatus,
)


class AttendanceFaceVerificationResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: AttendanceFaceVerificationStatus
    attempt_number: int = Field(alias="attemptNumber")
    can_retry: bool = Field(alias="canRetry")


class LivenessFailureResponse(BaseModel):
    status: Literal["liveness_failure"] = "liveness_failure"
