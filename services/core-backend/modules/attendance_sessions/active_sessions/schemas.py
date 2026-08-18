from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
    check_in_status: Literal["not_started", "open", "closed"] = Field(
        alias="checkInStatus"
    )
    late_after_at: datetime | None = Field(alias="lateAfterAt")
    venue: str | None = None
    requires_face_verification: bool = Field(alias="requiresFaceVerification")
    requires_geofence: bool = Field(alias="requiresGeofence")
    requires_qr: bool = Field(alias="requiresQr")
