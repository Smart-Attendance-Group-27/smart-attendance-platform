from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from modules.attendance_verification.geofence.types import (
    GeofenceDecision,
    GeofenceNextStep,
    GeofenceReason,
)


class CreateGeofenceAttemptRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    accuracy_m: float | None = Field(
        alias="accuracyM",
        ge=0,
        allow_inf_nan=False,
    )
    captured_at: datetime = Field(alias="capturedAt")
    mocked: bool = False

    @field_validator("captured_at")
    @classmethod
    def require_capture_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("capturedAt must include a timezone")
        return value


class CreateGeofenceAttemptResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    verification_attempt_id: UUID = Field(alias="verificationAttemptId")
    attempt_number: int = Field(alias="attemptNumber", ge=1)
    decision: GeofenceDecision
    distance_m: float = Field(alias="distanceM", ge=0)
    allowed_radius_m: float = Field(alias="allowedRadiusM", gt=0)
    next_step: GeofenceNextStep = Field(alias="nextStep")
    reason: GeofenceReason | None = None
