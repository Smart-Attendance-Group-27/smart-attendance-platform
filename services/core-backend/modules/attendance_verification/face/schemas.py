from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


PublicFaceStatus = Literal[
    "success",
    "face_not_detected",
    "multiple_faces",
    "verification_failure",
]


class AttendanceFaceVerificationResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: PublicFaceStatus
    attempt_number: int = Field(alias="attemptNumber")
    can_retry: bool = Field(alias="canRetry")

