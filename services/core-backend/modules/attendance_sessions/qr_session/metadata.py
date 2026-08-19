from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class QrBatchMetadata:
    # Compact shape shared by PostgreSQL reads and Redis cache entries. Dynamic
    # QR uses this to decide whether a batch/session can still emit QR values.
    id: UUID
    attendance_session_id: UUID
    attendance_session_status: str | None
    attendance_session_scheduled_end_at: datetime | None
    attendance_session_closed_at: datetime | None
    attendance_session_cancelled_at: datetime | None
    mode: str
    status: str | None
    activated_at: datetime
    deactivated_at: datetime | None
    refresh_interval_seconds: int | None
    expires_at: datetime
