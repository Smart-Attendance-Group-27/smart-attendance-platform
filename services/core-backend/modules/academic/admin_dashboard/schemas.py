from pydantic import BaseModel, ConfigDict, Field

from modules.academic.admin_dashboard.repository import AdminOverviewRecord

# No academic.attendance_policies table exists yet (see the Stage 5 migration
# proposal) — policyAlertsCount is honestly reported as 0 rather than invented,
# and academicSourceStatusLabel always reads "Not configured" since no real
# LMS/SIS sync integration exists in this codebase.
POLICY_ALERTS_COUNT = 0
ACADEMIC_SOURCE_STATUS_LABEL = "Not configured"


class AdminOverviewResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    active_users_count: int = Field(alias="activeUsersCount")
    configured_classrooms_count: int = Field(alias="configuredClassroomsCount")
    active_geofences_count: int = Field(alias="activeGeofencesCount")
    academic_source_status_label: str = Field(alias="academicSourceStatusLabel")
    policy_alerts_count: int = Field(alias="policyAlertsCount")

    @staticmethod
    def from_record(record: AdminOverviewRecord) -> "AdminOverviewResponse":
        return AdminOverviewResponse(
            active_users_count=record.active_users_count,
            configured_classrooms_count=record.configured_classrooms_count,
            active_geofences_count=record.active_geofences_count,
            academic_source_status_label=ACADEMIC_SOURCE_STATUS_LABEL,
            policy_alerts_count=POLICY_ALERTS_COUNT,
        )
