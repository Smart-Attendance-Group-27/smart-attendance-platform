from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


DEFAULT_QR_VALIDITY_SECONDS = 300
MIN_QR_VALIDITY_SECONDS = 30
MAX_QR_VALIDITY_SECONDS = 86400
DEFAULT_DYNAMIC_QR_REFRESH_INTERVAL_SECONDS = 15
MIN_DYNAMIC_QR_REFRESH_INTERVAL_SECONDS = 1
MAX_DYNAMIC_QR_REFRESH_INTERVAL_SECONDS = 300
QrSessionMode = Literal["static", "dynamic"]


class CreateQrSessionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mode: QrSessionMode = "static"
    valid_for_seconds: int = Field(
        default=DEFAULT_QR_VALIDITY_SECONDS,
        alias="validForSeconds",
        ge=MIN_QR_VALIDITY_SECONDS,
        le=MAX_QR_VALIDITY_SECONDS,
    )
    refresh_interval_seconds: int | None = Field(
        default=None,
        alias="refreshIntervalSeconds",
        ge=MIN_DYNAMIC_QR_REFRESH_INTERVAL_SECONDS,
        le=MAX_DYNAMIC_QR_REFRESH_INTERVAL_SECONDS,
    )

    @model_validator(mode="after")
    def validate_mode_refresh_interval(self) -> "CreateQrSessionRequest":
        if self.mode == "static" and self.refresh_interval_seconds is not None:
            raise ValueError(
                "refreshIntervalSeconds is only supported for dynamic QR sessions.",
            )

        if self.mode == "dynamic" and self.refresh_interval_seconds is None:
            self.refresh_interval_seconds = DEFAULT_DYNAMIC_QR_REFRESH_INTERVAL_SECONDS

        return self


class CreateQrSessionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    qr_session_id: UUID = Field(alias="qrSessionId")
    attendance_session_id: UUID = Field(alias="attendanceSessionId")
    mode: QrSessionMode
    qr_value: str | None = Field(default=None, alias="qrValue")
    refresh_interval_seconds: int | None = Field(
        default=None,
        alias="refreshIntervalSeconds",
    )
    status: str
    valid_from: datetime = Field(alias="validFrom")
    expires_at: datetime = Field(alias="expiresAt")


QrVerificationStatus = Literal["accepted", "invalid", "expired", "closed"]


class VerifyQrSessionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    qr_value: str = Field(alias="qrValue", min_length=1)


class VerifyQrSessionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    qr_session_id: UUID = Field(alias="qrSessionId")
    status: QrVerificationStatus
    verified_at: datetime = Field(alias="verifiedAt")


class CurrentDynamicQrSessionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    qr_session_id: UUID = Field(alias="qrSessionId")
    qr_value: str = Field(alias="qrValue")
    sequence: int
    valid_from: datetime = Field(alias="validFrom")
    expires_at: datetime = Field(alias="expiresAt")
