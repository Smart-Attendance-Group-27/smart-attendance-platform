from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from modules.attendance_verification.check_in.domain import StepRequirement
from modules.attendance_verification.session_overrides.domain import (
    GeofenceHealth,
    GeofenceWaiverReason,
    SessionVerificationOverride,
)
from modules.attendance_verification.session_overrides.service import (
    GeofenceWaiverResult,
    SessionVerificationPolicyView,
)


class GeofenceWaiverRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    reason_code: GeofenceWaiverReason = Field(alias="reasonCode")
    reason_text: str | None = Field(default=None, alias="reasonText", max_length=500)


class SessionVerificationOverrideResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    verification_factor: str = Field(alias="verificationFactor")
    scope: str
    previous_policy: str = Field(alias="previousPolicy")
    new_policy: str = Field(alias="newPolicy")
    reason_code: str = Field(alias="reasonCode")
    reason_text: str | None = Field(alias="reasonText")
    performed_by: UUID = Field(alias="performedBy")
    performed_by_name: str | None = Field(alias="performedByName")
    performed_at: datetime = Field(alias="performedAt")
    affected_student_count: int = Field(alias="affectedStudentCount")

    @staticmethod
    def from_domain(value: SessionVerificationOverride) -> "SessionVerificationOverrideResponse":
        return SessionVerificationOverrideResponse(
            id=value.id,
            verification_factor=value.verification_factor.value,
            scope=value.scope.value,
            previous_policy=value.previous_policy.value,
            new_policy=value.new_policy.value,
            reason_code=value.reason_code.value,
            reason_text=value.reason_text,
            performed_by=value.performed_by,
            performed_by_name=value.performed_by_name,
            performed_at=value.performed_at,
            affected_student_count=value.affected_student_count,
        )


class GeofenceHealthResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    attempted: int
    passed: int
    failed: int
    failure_rate_percent: float = Field(alias="failureRatePercent")
    warning: bool
    warning_minimum_attempts: int = Field(alias="warningMinimumAttempts")
    warning_failure_rate_percent: float = Field(alias="warningFailureRatePercent")

    @staticmethod
    def from_domain(value: GeofenceHealth) -> "GeofenceHealthResponse":
        return GeofenceHealthResponse(
            attempted=value.attempted,
            passed=value.passed,
            failed=value.failed,
            failure_rate_percent=round(value.failure_rate * 100, 1),
            warning=value.warning,
            warning_minimum_attempts=value.minimum_attempts,
            warning_failure_rate_percent=round(value.warning_failure_rate * 100, 1),
        )


class SessionVerificationPolicyResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: UUID = Field(alias="sessionId")
    geofence: StepRequirement
    face: StepRequirement
    geofence_waiver: SessionVerificationOverrideResponse | None = Field(alias="geofenceWaiver")
    geofence_health: GeofenceHealthResponse = Field(alias="geofenceHealth")

    @staticmethod
    def from_view(view: SessionVerificationPolicyView) -> "SessionVerificationPolicyResponse":
        return SessionVerificationPolicyResponse(
            session_id=view.session_id,
            geofence=view.policy.geofence,
            face=view.policy.face,
            geofence_waiver=(
                SessionVerificationOverrideResponse.from_domain(view.geofence_waiver)
                if view.geofence_waiver is not None
                else None
            ),
            geofence_health=GeofenceHealthResponse.from_domain(view.geofence_health),
        )


class GeofenceWaiverResponse(SessionVerificationPolicyResponse):
    created: bool
    reopened_attempt_count: int = Field(alias="reopenedAttemptCount")

    @staticmethod
    def from_result(result: GeofenceWaiverResult) -> "GeofenceWaiverResponse":
        base = SessionVerificationPolicyResponse.from_view(result.view)
        return GeofenceWaiverResponse(
            **base.model_dump(),
            created=result.created,
            reopened_attempt_count=result.reopened_attempt_count,
        )


__all__ = [
    "GeofenceHealthResponse",
    "GeofenceWaiverRequest",
    "GeofenceWaiverResponse",
    "SessionVerificationOverrideResponse",
    "SessionVerificationPolicyResponse",
]
