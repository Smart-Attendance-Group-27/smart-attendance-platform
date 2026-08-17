from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from modules.attendance_sessions.lecturer_sessions.repository import LecturerSessionRecord


def derive_session_status(record: LecturerSessionRecord) -> str:
    """Derives a status string from timestamps rather than a DB enum.

    attendance_session.sessions.status has no CHECK constraint and existing
    code only ever checks for the literal 'active' — cancelled_at/closed_at/
    activated_at are the real source of truth, so status is computed from
    them here instead of trusting the raw column.
    """
    if record.cancelled_at is not None:
        return "cancelled"
    if record.closed_at is not None:
        return "closed"
    if record.activated_at is not None:
        return "active"
    return "scheduled"


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
    requires_face_verification: bool = Field(alias="requiresFaceVerification")
    requires_geofence: bool = Field(alias="requiresGeofence")
    requires_qr: bool = Field(alias="requiresQr")
    enrolled_count: int = Field(alias="enrolledCount")
    present_count: int = Field(alias="presentCount")
    late_count: int = Field(alias="lateCount")
    pending_review_count: int = Field(alias="pendingReviewCount")

    @staticmethod
    def from_record(record: LecturerSessionRecord) -> "LecturerSessionResponse":
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
            requires_face_verification=record.requires_face_verification,
            requires_geofence=record.requires_geofence,
            requires_qr=record.requires_qr,
            enrolled_count=record.enrolled_count,
            present_count=record.present_count,
            late_count=record.late_count,
            pending_review_count=record.pending_review_count,
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
    qr_status: str | None = Field(alias="qrStatus")
    attendance_status: str | None = Field(alias="attendanceStatus")
    review_status: str | None = Field(alias="reviewStatus")
    checked_in_at: datetime | None = Field(alias="checkedInAt")
