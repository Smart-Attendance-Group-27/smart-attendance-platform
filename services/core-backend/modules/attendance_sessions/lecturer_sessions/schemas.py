from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from modules.attendance_sessions.lecturer_sessions.repository import LecturerSessionRecord
from modules.attendance_verification.finalization.types import FinalizationSummary


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    timetable_entry_id: UUID = Field(alias="timetableEntryId")
    session_title: str = Field(alias="sessionTitle", min_length=1, max_length=255)
    session_type: str = Field(default="lecture", alias="sessionType", min_length=1, max_length=20)
    scheduled_start_at: datetime = Field(alias="scheduledStartAt")
    scheduled_end_at: datetime = Field(alias="scheduledEndAt")
    check_in_opens_at: datetime | None = Field(default=None, alias="checkInOpensAt")
    check_in_closes_at: datetime | None = Field(default=None, alias="checkInClosesAt")
    late_after_at: datetime | None = Field(default=None, alias="lateAfterAt")
    requires_face_verification: bool = Field(default=True, alias="requiresFaceVerification")
    requires_geofence: bool = Field(default=True, alias="requiresGeofence")
    requires_qr: bool = Field(default=False, alias="requiresQr")


class CancelSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]


def derive_session_status(record: LecturerSessionRecord) -> str:
    """Derives a status string from timestamps rather than a DB enum.

    attendance_session.sessions.status has no CHECK constraint, and sessions
    closed before 'closed' was stored still read 'active'. cancelled_at/
    closed_at/activated_at are the source of truth, so status is computed
    from them here instead of trusting the raw column.
    """
    if record.cancelled_at is not None:
        return "cancelled"
    if record.closed_at is not None:
        return "closed"
    if record.activated_at is not None:
        return "active"
    return "scheduled"


class FinalizationResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    enrolled_count: int = Field(alias="enrolledCount")
    present_count: int = Field(alias="presentCount")
    late_count: int = Field(alias="lateCount")
    absent_count: int = Field(alias="absentCount")
    kept_manual_count: int = Field(alias="keptManualCount")
    reconciled_count: int = Field(alias="reconciledCount")
    deactivated_qr_batch_count: int = Field(alias="deactivatedQrBatchCount")
    finalized_at: datetime = Field(alias="finalizedAt")

    @staticmethod
    def from_summary(summary: FinalizationSummary) -> "FinalizationResponse":
        return FinalizationResponse(
            enrolled_count=summary.enrolled,
            present_count=summary.present,
            late_count=summary.late,
            absent_count=summary.absent,
            kept_manual_count=summary.kept_manual,
            reconciled_count=len(summary.reconciled_student_ids),
            deactivated_qr_batch_count=len(summary.deactivated_qr_batch_ids),
            finalized_at=summary.finalized_at,
        )


class LecturerSessionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    course_offering_id: UUID = Field(alias="courseOfferingId")
    course_code: str = Field(alias="courseCode")
    course_name: str = Field(alias="courseName")
    classroom_code: str | None = Field(alias="classroomCode")
    status: str
    scheduled_start_at: datetime = Field(alias="scheduledStartAt")
    scheduled_end_at: datetime = Field(alias="scheduledEndAt")
    check_in_opens_at: datetime | None = Field(alias="checkInOpensAt")
    check_in_closes_at: datetime | None = Field(alias="checkInClosesAt")
    late_after_at: datetime | None = Field(alias="lateAfterAt")
    activated_at: datetime | None = Field(alias="activatedAt")
    closed_at: datetime | None = Field(alias="closedAt")
    cancelled_at: datetime | None = Field(alias="cancelledAt")
    cancellation_reason: str | None = Field(alias="cancellationReason")
    requires_face_verification: bool = Field(alias="requiresFaceVerification")
    requires_geofence: bool = Field(alias="requiresGeofence")
    requires_qr: bool = Field(alias="requiresQr")
    enrolled_count: int = Field(alias="enrolledCount")
    present_count: int = Field(alias="presentCount")
    late_count: int = Field(alias="lateCount")
    pending_review_count: int = Field(alias="pendingReviewCount")
    checked_in_count: int = Field(alias="checkedInCount")
    late_checked_in_count: int = Field(alias="lateCheckedInCount")
    not_checked_in_count: int = Field(alias="notCheckedInCount")
    failed_verification_count: int = Field(alias="failedVerificationCount")
    absent_count: int = Field(alias="absentCount")
    manual_count: int = Field(alias="manualCount")
    finalization: FinalizationResponse | None = None

    @staticmethod
    def from_record(
        record: LecturerSessionRecord,
        finalization: FinalizationSummary | None = None,
    ) -> "LecturerSessionResponse":
        not_checked_in_count = (
            record.enrolled_count
            - record.checked_in_count
            - record.late_checked_in_count
            - record.failed_verification_count
        )
        return LecturerSessionResponse(
            id=record.id,
            course_offering_id=record.course_offering_id,
            course_code=record.course_code or "",
            course_name=record.course_name or "",
            classroom_code=record.classroom_code,
            status=derive_session_status(record),
            scheduled_start_at=record.scheduled_start_at,
            scheduled_end_at=record.scheduled_end_at,
            check_in_opens_at=record.check_in_opens_at,
            check_in_closes_at=record.check_in_closes_at,
            late_after_at=record.late_after_at,
            activated_at=record.activated_at,
            closed_at=record.closed_at,
            cancelled_at=record.cancelled_at,
            cancellation_reason=record.cancellation_reason,
            requires_face_verification=record.requires_face_verification,
            requires_geofence=record.requires_geofence,
            requires_qr=record.requires_qr,
            enrolled_count=record.enrolled_count,
            present_count=record.present_count,
            late_count=record.late_count,
            pending_review_count=record.pending_review_count,
            checked_in_count=record.checked_in_count,
            late_checked_in_count=record.late_checked_in_count,
            not_checked_in_count=max(not_checked_in_count, 0),
            failed_verification_count=record.failed_verification_count,
            absent_count=record.absent_count,
            manual_count=record.manual_count,
            finalization=(
                FinalizationResponse.from_summary(finalization)
                if finalization is not None
                else None
            ),
        )


class SessionStudentResponse(BaseModel):
    """Deliberately excludes raw biometric data (embeddings/images) and precise
    coordinates — only verification outcomes/scores needed for lecturer review."""

    model_config = ConfigDict(populate_by_name=True)

    student_id: UUID = Field(alias="studentId")
    registration_number: str = Field(alias="registrationNumber")
    full_name: str = Field(alias="fullName")
    verification_status: str | None = Field(alias="verificationStatus")
    geofence_status: str | None = Field(alias="geofenceStatus")
    face_status: str | None = Field(alias="faceStatus")
    face_similarity_score: float | None = Field(alias="faceSimilarityScore")
    face_liveness_passed: bool | None = Field(alias="faceLivenessPassed")
    attendance_status: str | None = Field(alias="attendanceStatus")
    review_status: str | None = Field(alias="reviewStatus")
    checked_in_at: datetime | None = Field(alias="checkedInAt")
    # Added in O4. Defaulted so route.py can populate them one at a time
    # instead of needing every field in the same change.
    failure_reason: str | None = Field(default=None, alias="failureReason")
    initial_check_in_status: str | None = Field(default=None, alias="initialCheckInStatus")
    record_source: str | None = Field(default=None, alias="recordSource")
    manual_reason: str | None = Field(default=None, alias="manualReason")
    record_updated_at: datetime | None = Field(default=None, alias="recordUpdatedAt")
    qr_required_count: int | None = Field(default=None, alias="qrRequiredCount")
    qr_passed_count: int | None = Field(default=None, alias="qrPassedCount")
