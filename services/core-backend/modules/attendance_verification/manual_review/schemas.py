from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from modules.attendance_verification.manual_review.repository import ManualReviewQueueItemRecord


class ManualReviewDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    RETRY = "retry"
    ESCALATE = "escalate"


class ManualReviewDecisionRequest(BaseModel):
    decision: ManualReviewDecision
    reason: str | None = Field(default=None, max_length=1000)


class ManualReviewQueueItemResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    verification_attempt_id: UUID = Field(alias="verificationAttemptId")
    session_id: UUID = Field(alias="sessionId")
    course_code: str = Field(alias="courseCode")
    course_name: str = Field(alias="courseName")
    classroom_code: str | None = Field(alias="classroomCode")
    scheduled_start_at: datetime = Field(alias="scheduledStartAt")
    student_id: UUID = Field(alias="studentId")
    registration_number: str = Field(alias="registrationNumber")
    full_name: str = Field(alias="fullName")
    failure_reason: str | None = Field(alias="failureReason")
    started_at: datetime | None = Field(alias="startedAt")
    completed_at: datetime | None = Field(alias="completedAt")
    geofence_status: str | None = Field(alias="geofenceStatus")
    geofence_failure_reason: str | None = Field(alias="geofenceFailureReason")
    face_status: str | None = Field(alias="faceStatus")
    face_similarity_score: float | None = Field(alias="faceSimilarityScore")
    face_liveness_passed: bool | None = Field(alias="faceLivenessPassed")
    qr_status: str | None = Field(alias="qrStatus")
    review_status: str = Field(alias="reviewStatus")
    decision_reason: str | None = Field(alias="decisionReason")
    reviewed_at: datetime | None = Field(alias="reviewedAt")

    @staticmethod
    def from_record(record: ManualReviewQueueItemRecord) -> "ManualReviewQueueItemResponse":
        return ManualReviewQueueItemResponse(
            verification_attempt_id=record.verification_attempt_id,
            session_id=record.session_id,
            course_code=record.course_code or "",
            course_name=record.course_name or "",
            classroom_code=record.classroom_code,
            scheduled_start_at=record.scheduled_start_at,
            student_id=record.student_id,
            registration_number=record.registration_number or "",
            full_name=record.full_name,
            failure_reason=record.failure_reason,
            started_at=record.started_at,
            completed_at=record.completed_at,
            geofence_status=record.geofence_status,
            geofence_failure_reason=record.geofence_failure_reason,
            face_status=record.face_status,
            face_similarity_score=(
                float(record.face_similarity_score)
                if record.face_similarity_score is not None
                else None
            ),
            face_liveness_passed=record.face_liveness_passed,
            qr_status=record.qr_status,
            review_status=record.review_status or "pending",
            decision_reason=record.decision_reason,
            reviewed_at=record.reviewed_at,
        )
