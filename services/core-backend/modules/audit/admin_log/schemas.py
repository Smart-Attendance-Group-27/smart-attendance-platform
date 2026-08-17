from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from modules.audit.admin_log.repository import AuditLogRecord


class AuditLogEntryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    occurred_at: datetime = Field(alias="occurredAt")
    actor_user_id: UUID | None = Field(alias="actorUserId")
    actor_type: str = Field(alias="actorType")
    actor_name: str = Field(alias="actorName")
    action: str
    entity_type: str = Field(alias="entityType")
    entity_id: UUID | None = Field(alias="entityId")
    outcome: str = Field(alias="outcome")
    failure_reason: str | None = Field(alias="failureReason")

    @staticmethod
    def from_record(record: AuditLogRecord) -> "AuditLogEntryResponse":
        return AuditLogEntryResponse(
            id=record.id,
            occurred_at=record.occurred_at,
            actor_user_id=record.actor_user_id,
            actor_type=record.actor_type or "system",
            actor_name=record.actor_name,
            action=record.action,
            entity_type=record.entity_type,
            entity_id=record.entity_id,
            outcome=record.outcome or "success",
            failure_reason=record.failure_reason,
        )
