from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from modules.attendance_sessions.qr_session.evidence import QrBatchParticipation, StudentQrBatch
from modules.attendance_sessions.qr_session.service import StudentQrProgress


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
    batch_passed: bool = Field(alias="batchPassed")
    already_passed: bool = Field(alias="alreadyPassed")
    required_for_student: bool = Field(alias="requiredForStudent")


class CurrentDynamicQrSessionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    qr_session_id: UUID = Field(alias="qrSessionId")
    qr_value: str = Field(alias="qrValue")
    sequence: int
    valid_from: datetime = Field(alias="validFrom")
    expires_at: datetime = Field(alias="expiresAt")


class StudentQrActiveBatchResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    qr_session_id: UUID = Field(alias="qrSessionId")
    mode: QrSessionMode
    activated_at: datetime = Field(alias="activatedAt")
    expires_at: datetime = Field(alias="expiresAt")
    required: bool
    passed: bool

    @staticmethod
    def from_domain(batch: StudentQrBatch) -> "StudentQrActiveBatchResponse":
        return StudentQrActiveBatchResponse(
            qr_session_id=batch.qr_session_id, mode=batch.mode,
            activated_at=batch.activated_at, expires_at=batch.expires_at,
            required=batch.required, passed=batch.passed,
        )


class StudentQrBatchResponse(StudentQrActiveBatchResponse):
    deactivated_at: datetime | None = Field(alias="deactivatedAt")
    voided: bool

    @staticmethod
    def from_domain(batch: StudentQrBatch) -> "StudentQrBatchResponse":
        return StudentQrBatchResponse(
            qr_session_id=batch.qr_session_id, mode=batch.mode,
            activated_at=batch.activated_at, deactivated_at=batch.deactivated_at,
            expires_at=batch.expires_at, voided=batch.voided,
            required=batch.required, passed=batch.passed,
        )


class StudentQrProgressResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: UUID = Field(alias="sessionId")
    qr_enabled: bool = Field(alias="qrEnabled")
    checked_in_at: datetime | None = Field(alias="checkedInAt")
    required_count: int = Field(alias="requiredCount")
    passed_count: int = Field(alias="passedCount")
    active_batch: StudentQrActiveBatchResponse | None = Field(alias="activeBatch")
    batches: list[StudentQrBatchResponse]

    @staticmethod
    def from_domain(progress: StudentQrProgress) -> "StudentQrProgressResponse":
        return StudentQrProgressResponse(
            session_id=progress.session_id, qr_enabled=progress.qr_enabled,
            checked_in_at=progress.checked_in_at,
            required_count=progress.required_count, passed_count=progress.passed_count,
            active_batch=(StudentQrActiveBatchResponse.from_domain(progress.active_batch)
                          if progress.active_batch else None),
            batches=[StudentQrBatchResponse.from_domain(batch) for batch in progress.batches],
        )


class LecturerQrBatchResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    qr_session_id: UUID = Field(alias="qrSessionId")
    mode: QrSessionMode
    status: str
    activated_at: datetime = Field(alias="activatedAt")
    deactivated_at: datetime | None = Field(alias="deactivatedAt")
    expires_at: datetime = Field(alias="expiresAt")
    voided: bool
    void_reason: str | None = Field(alias="voidReason")
    required_student_count: int = Field(alias="requiredStudentCount")
    passed_student_count: int = Field(alias="passedStudentCount")

    @staticmethod
    def from_domain(batch: QrBatchParticipation) -> "LecturerQrBatchResponse":
        return LecturerQrBatchResponse(
            qr_session_id=batch.qr_session_id, mode=batch.mode, status=batch.status,
            activated_at=batch.activated_at, deactivated_at=batch.deactivated_at,
            expires_at=batch.expires_at, voided=batch.voided, void_reason=batch.void_reason,
            required_student_count=batch.required_student_count,
            passed_student_count=batch.passed_student_count,
        )
