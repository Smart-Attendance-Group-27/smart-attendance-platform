from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


DEFAULT_QR_VALIDITY_SECONDS = 300
MIN_QR_VALIDITY_SECONDS = 30
MAX_QR_VALIDITY_SECONDS = 86400


class CreateQrSessionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    valid_for_seconds: int = Field(
        default=DEFAULT_QR_VALIDITY_SECONDS,
        alias="validForSeconds",
        ge=MIN_QR_VALIDITY_SECONDS,
        le=MAX_QR_VALIDITY_SECONDS,
    )


class CreateQrSessionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    qr_session_id: UUID = Field(alias="qrSessionId")
    attendance_session_id: UUID = Field(alias="attendanceSessionId")
    qr_value: str = Field(alias="qrValue")
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
