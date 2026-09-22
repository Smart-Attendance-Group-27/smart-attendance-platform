from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from modules.attendance_sessions.active_sessions.state_service import (
    SessionState,
    StudentAttendanceState,
)


class ActiveAttendanceSessionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    course_code: str = Field(alias="courseCode")
    course_name: str = Field(alias="courseName")
    session_title: str = Field(alias="sessionTitle")
    session_type: str = Field(alias="sessionType")
    lecturer_names: str | None = Field(alias="lecturerNames")
    scheduled_start_at: datetime = Field(alias="scheduledStartAt")
    scheduled_end_at: datetime = Field(alias="scheduledEndAt")
    check_in_opens_at: datetime = Field(alias="checkInOpensAt")
    check_in_closes_at: datetime = Field(alias="checkInClosesAt")
    late_after_at: datetime | None = Field(alias="lateAfterAt")
    venue: str | None = None
    requires_face_verification: bool = Field(alias="requiresFaceVerification")
    requires_geofence: bool = Field(alias="requiresGeofence")
    requires_qr: bool = Field(alias="requiresQr")
    attempt_status: str | None = Field(alias="attemptStatus")
    initial_check_in_status: str | None = Field(alias="initialCheckInStatus")
    checked_in_at: datetime | None = Field(alias="checkedInAt")
    final_attendance_status: str | None = Field(alias="finalAttendanceStatus")


class VerificationStateResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    attempt_status: str | None = Field(alias="attemptStatus")
    failure_reason: str | None = Field(alias="failureReason")
    geofence_status: str | None = Field(alias="geofenceStatus")
    face_status: str | None = Field(alias="faceStatus")
    liveness_passed: bool | None = Field(alias="livenessPassed")


class InitialCheckInStateResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    checked_in_at: datetime = Field(alias="checkedInAt")


class FinalAttendanceStateResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    source: str
    decided_at: datetime = Field(alias="decidedAt")


class StudentAttendanceStateResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: UUID = Field(alias="sessionId")
    course_code: str = Field(alias="courseCode")
    course_name: str = Field(alias="courseName")
    session_title: str = Field(alias="sessionTitle")
    session_type: str = Field(alias="sessionType")
    session_state: SessionState = Field(alias="sessionState")
    cancelled_at: datetime | None = Field(alias="cancelledAt")
    cancellation_reason: str | None = Field(alias="cancellationReason")
    scheduled_start_at: datetime = Field(alias="scheduledStartAt")
    scheduled_end_at: datetime = Field(alias="scheduledEndAt")
    check_in_opens_at: datetime | None = Field(alias="checkInOpensAt")
    check_in_closes_at: datetime | None = Field(alias="checkInClosesAt")
    late_after_at: datetime | None = Field(alias="lateAfterAt")
    requires_face_verification: bool = Field(alias="requiresFaceVerification")
    qr_enabled: bool = Field(alias="qrEnabled")
    can_start_check_in: bool = Field(alias="canStartCheckIn")
    verification: VerificationStateResponse
    initial_check_in: InitialCheckInStateResponse | None = Field(alias="initialCheckIn")
    final_attendance: FinalAttendanceStateResponse | None = Field(alias="finalAttendance")

    @staticmethod
    def from_domain(state: StudentAttendanceState) -> "StudentAttendanceStateResponse":
        return StudentAttendanceStateResponse(
            session_id=state.session_id,
            course_code=state.course_code or "",
            course_name=state.course_name or "",
            session_title=state.session_title or "",
            session_type=state.session_type or "",
            session_state=state.session_state,
            cancelled_at=state.cancelled_at,
            cancellation_reason=state.cancellation_reason,
            scheduled_start_at=state.scheduled_start_at,
            scheduled_end_at=state.scheduled_end_at,
            check_in_opens_at=state.check_in_opens_at,
            check_in_closes_at=state.check_in_closes_at,
            late_after_at=state.late_after_at,
            requires_face_verification=state.requires_face_verification,
            qr_enabled=state.qr_enabled,
            can_start_check_in=state.can_start_check_in,
            verification=VerificationStateResponse(
                attempt_status=state.verification.attempt_status,
                failure_reason=state.verification.failure_reason,
                geofence_status=state.verification.geofence_status,
                face_status=state.verification.face_status,
                liveness_passed=state.verification.liveness_passed,
            ),
            initial_check_in=(
                InitialCheckInStateResponse(
                    status=state.initial_check_in.status,
                    checked_in_at=state.initial_check_in.checked_in_at,
                )
                if state.initial_check_in is not None
                else None
            ),
            final_attendance=(
                FinalAttendanceStateResponse(
                    status=state.final_attendance.status,
                    source=state.final_attendance.source,
                    decided_at=state.final_attendance.decided_at,
                )
                if state.final_attendance is not None
                else None
            ),
        )
