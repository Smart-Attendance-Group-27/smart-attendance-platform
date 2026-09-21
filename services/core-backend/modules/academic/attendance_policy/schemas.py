from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator


class PolicyWriteRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    check_in_window_minutes: StrictInt = Field(alias="checkInWindowMinutes", ge=1, le=180)
    late_threshold_minutes: StrictInt = Field(alias="lateThresholdMinutes", ge=0)
    qr_default_validity_minutes: StrictInt = Field(alias="qrDefaultValidityMinutes", ge=1, le=60)
    face_confidence_threshold_percent: StrictInt = Field(
        alias="faceConfidenceThresholdPercent", ge=50, le=99,
    )

    @model_validator(mode="after")
    def late_threshold_fits_window(self) -> "PolicyWriteRequest":
        if self.late_threshold_minutes > self.check_in_window_minutes:
            raise ValueError("Late threshold cannot exceed the check-in window.")
        return self


class PolicyResponse(PolicyWriteRequest):
    updated_at: datetime = Field(alias="updatedAt")
    updated_by_name: str | None = Field(alias="updatedByName")
