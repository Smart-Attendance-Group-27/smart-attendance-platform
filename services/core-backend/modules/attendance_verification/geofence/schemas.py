from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from modules.attendance_verification.check_in.schemas import InitialCheckInPayload
from modules.attendance_verification.geofence.types import (
    GeofenceDecision,
    GeofenceNextStep,
    GeofenceReason,
)


class CreateGeofenceAttemptRequest(BaseModel):
    # Validate the wire format before service logic. Reject extra fields and
    # non-finite/out-of-range coordinates; camelCase aliases match the mobile API.
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    # Reported horizontal error in metres. A null value produces a policy retry.
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
        # A timezone is required so reading age can be compared to server UTC time.
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("capturedAt must include a timezone")
        return value


class CreateGeofenceAttemptResponse(BaseModel):
    # The decision describes this reading; initialCheckIn describes the combined
    # initial result. Neither field is the final attendance outcome at closure.
    model_config = ConfigDict(populate_by_name=True)

    verification_attempt_id: UUID = Field(alias="verificationAttemptId")
    attempt_number: int = Field(alias="attemptNumber", ge=1)
    decision: GeofenceDecision
    distance_m: float = Field(alias="distanceM", ge=0)
    allowed_radius_m: float = Field(alias="allowedRadiusM", gt=0)
    next_step: GeofenceNextStep = Field(alias="nextStep")
    reason: GeofenceReason | None = None
    # Populated when this pass was the last step the session required.
    initial_check_in: InitialCheckInPayload | None = Field(
        alias="initialCheckIn",
        default=None,
    )


class StartVerificationResponse(BaseModel):
    """An attempt opened without a location reading (geofence waived)."""

    model_config = ConfigDict(populate_by_name=True)

    verification_attempt_id: UUID = Field(alias="verificationAttemptId")
    geofence_requirement: str = Field(alias="geofenceRequirement")
    next_step: GeofenceNextStep = Field(alias="nextStep")
    initial_check_in: InitialCheckInPayload | None = Field(
        alias="initialCheckIn",
        default=None,
    )
