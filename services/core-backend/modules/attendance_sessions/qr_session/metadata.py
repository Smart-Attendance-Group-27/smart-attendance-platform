from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class QrBatchMetadata:
    id: UUID
    attendance_session_id: UUID
    mode: str
    status: str | None
    activated_at: datetime
    deactivated_at: datetime | None
    refresh_interval_seconds: int | None
    expires_at: datetime
