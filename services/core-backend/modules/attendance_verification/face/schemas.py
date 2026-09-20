from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from modules.attendance_verification.check_in.schemas import InitialCheckInPayload


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
    # Populated when this pass was the last step the session required.
    initial_check_in: InitialCheckInPayload | None = Field(
        alias="initialCheckIn",
        default=None,
    )


class AttendanceFaceProgressResponse(BaseModel):
    status: Literal["passed", "required"]
