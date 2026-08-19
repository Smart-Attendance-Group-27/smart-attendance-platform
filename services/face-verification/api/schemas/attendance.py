from pydantic import BaseModel, ConfigDict, Field

from services.attendance_face_verification_service import (
    AttendanceFaceVerificationStatus,
)


class AttendanceFaceVerificationResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: AttendanceFaceVerificationStatus
    message: str
    similarity_score: float | None = Field(default=None, alias="similarityScore")
