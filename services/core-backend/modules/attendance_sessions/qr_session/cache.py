import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from redis import RedisError
from redis.asyncio import Redis

from modules.attendance_sessions.qr_session.metadata import QrBatchMetadata


logger = logging.getLogger(__name__)

QR_BATCH_CACHE_KEY_PREFIX = "qr:batch"


class QrBatchMetadataCache:
    def __init__(self, redis_client: Redis | None) -> None:
        self._redis_client = redis_client

    async def get_qr_batch_cache(
        self,
        qr_session_id: UUID,
    ) -> QrBatchMetadata | None:
        if self._redis_client is None:
            return None

        try:
            cached_value = await self._redis_client.get(
                self._build_cache_key(qr_session_id),
            )
        except RedisError:
            logger.warning("QR batch metadata cache read failed; falling back to database.")
            return None

        if cached_value is None:
            return None

        try:
            return self._deserialize_metadata(cached_value)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            logger.warning("QR batch metadata cache entry was invalid; falling back to database.")
            return None

    async def set_qr_batch_cache(
        self,
        qr_session_id: UUID,
        metadata: QrBatchMetadata,
        ttl_seconds: int,
    ) -> None:
        if self._redis_client is None or ttl_seconds <= 0:
            return

        try:
            await self._redis_client.set(
                self._build_cache_key(qr_session_id),
                self._serialize_metadata(metadata),
                ex=ttl_seconds,
            )
        except RedisError:
            logger.warning("QR batch metadata cache write failed; continuing without cache.")

    async def delete_qr_batch_cache(self, qr_session_id: UUID) -> None:
        if self._redis_client is None:
            return

        try:
            await self._redis_client.delete(self._build_cache_key(qr_session_id))
        except RedisError:
            logger.warning("QR batch metadata cache delete failed; continuing without cache.")

    @staticmethod
    def _build_cache_key(qr_session_id: UUID) -> str:
        return f"{QR_BATCH_CACHE_KEY_PREFIX}:{qr_session_id}"

    @staticmethod
    def _serialize_metadata(metadata: QrBatchMetadata) -> str:
        payload = {
            "id": str(metadata.id),
            "attendanceSessionId": str(metadata.attendance_session_id),
            "mode": metadata.mode,
            "status": metadata.status,
            "activatedAt": metadata.activated_at.isoformat(),
            "deactivatedAt": (
                metadata.deactivated_at.isoformat()
                if metadata.deactivated_at is not None
                else None
            ),
            "refreshIntervalSeconds": metadata.refresh_interval_seconds,
            "expiresAt": metadata.expires_at.isoformat(),
        }
        return json.dumps(payload, separators=(",", ":"))

    @staticmethod
    def _deserialize_metadata(payload: str) -> QrBatchMetadata:
        value = json.loads(payload)
        return QrBatchMetadata(
            id=UUID(value["id"]),
            attendance_session_id=UUID(value["attendanceSessionId"]),
            mode=value["mode"],
            status=value["status"],
            activated_at=_parse_datetime(value["activatedAt"]),
            deactivated_at=(
                _parse_datetime(value["deactivatedAt"])
                if value["deactivatedAt"] is not None
                else None
            ),
            refresh_interval_seconds=value["refreshIntervalSeconds"],
            expires_at=_parse_datetime(value["expiresAt"]),
        )


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
