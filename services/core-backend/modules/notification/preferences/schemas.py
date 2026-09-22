from pydantic import BaseModel, ConfigDict, Field

from modules.notification.preferences.repository import NotificationPreferenceRecord


class NotificationPreferenceResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type_code: str = Field(alias="typeCode")
    description: str
    in_app_enabled: bool = Field(alias="inAppEnabled")
    push_enabled: bool = Field(alias="pushEnabled")
    is_customized: bool = Field(alias="isCustomized")

    @classmethod
    def from_record(
        cls,
        record: NotificationPreferenceRecord,
    ) -> "NotificationPreferenceResponse":
        return cls(
            type_code=record.type_code,
            description=record.description,
            in_app_enabled=record.in_app_enabled,
            push_enabled=record.push_enabled,
            is_customized=record.is_customized,
        )


class NotificationPreferenceUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type_code: str = Field(alias="typeCode", min_length=1, max_length=50)
    in_app_enabled: bool = Field(alias="inAppEnabled")
    push_enabled: bool = Field(alias="pushEnabled")


class NotificationPreferencesUpdateRequest(BaseModel):
    preferences: list[NotificationPreferenceUpdate] = Field(min_length=1)
