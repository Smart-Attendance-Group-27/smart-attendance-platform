from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StudentNotificationResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    title: str
    message: str
    type: str
    code: str
    created_at: datetime = Field(alias="createdAt")
    is_read: bool = Field(alias="isRead")
    related_id: UUID | None = Field(default=None, alias="relatedId")
    related_entity_type: str | None = Field(default=None, alias="relatedEntityType")
