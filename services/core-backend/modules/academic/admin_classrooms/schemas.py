from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from modules.academic.admin_classrooms.repository import BuildingRecord, ClassroomRecord

ACTIVE_STATUS = "active"
INACTIVE_STATUS = "inactive"


class BuildingResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    building_name: str = Field(alias="buildingName")
    status: str | None

    @staticmethod
    def from_record(record: BuildingRecord) -> "BuildingResponse":
        return BuildingResponse(
            id=record.id,
            building_name=record.building_name or "",
            status=record.status,
        )


class ClassroomResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    building_id: UUID = Field(alias="buildingId")
    building_name: str = Field(alias="buildingName")
    classroom_code: str = Field(alias="classroomCode")
    floor_number: int | None = Field(alias="floorNumber")
    capacity: int | None
    latitude: float
    longitude: float
    default_geofence_radius_m: float = Field(alias="defaultGeofenceRadiusM")
    status: str
    assigned_courses_count: int = Field(alias="assignedCoursesCount")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    @staticmethod
    def from_record(record: ClassroomRecord) -> "ClassroomResponse":
        return ClassroomResponse(
            id=record.id,
            building_id=record.building_id,
            building_name=record.building_name or "",
            classroom_code=record.classroom_code or "",
            floor_number=record.floor_number,
            capacity=record.capacity,
            latitude=float(record.latitude) if record.latitude is not None else 0.0,
            longitude=float(record.longitude) if record.longitude is not None else 0.0,
            default_geofence_radius_m=(
                float(record.default_geofence_radius_m)
                if record.default_geofence_radius_m is not None
                else 0.0
            ),
            status=record.status or "",
            assigned_courses_count=record.assigned_courses_count,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class ClassroomWriteRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    building_id: UUID = Field(alias="buildingId")
    classroom_code: str = Field(alias="classroomCode", min_length=1, max_length=30)
    floor_number: int | None = Field(default=None, alias="floorNumber")
    capacity: int | None = Field(default=None, ge=1)
    latitude: Decimal = Field(ge=-90, le=90)
    longitude: Decimal = Field(ge=-180, le=180)
    default_geofence_radius_m: Decimal = Field(alias="defaultGeofenceRadiusM", gt=0)
    status: str = Field(default=ACTIVE_STATUS)
