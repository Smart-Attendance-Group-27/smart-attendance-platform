from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RegisterDeviceRequest(BaseModel):
    """Payload sent by the mobile app after the user grants notification permission."""

    model_config = ConfigDict(populate_by_name=True)

    expo_push_token: str = Field(alias="expoPushToken")
    platform: str  # "android" | "ios" | "web"


class DeviceTokenResponse(BaseModel):
    """Safe view of the registered device token returned to the caller."""

    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    platform: str
    is_active: bool = Field(alias="isActive")
    registered_at: datetime = Field(alias="registeredAt")
