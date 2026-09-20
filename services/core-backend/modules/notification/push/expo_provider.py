import logging

import httpx

from modules.notification.push.exception import ExpoNetworkError, ExpoServiceError
from modules.notification.push.provider import PushMessage, PushReceipt

logger = logging.getLogger(__name__)

_EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
_EXPO_CHUNK_SIZE = 100          # Expo limit per request
_INVALID_TOKEN_REASON = "DeviceNotRegistered"


class ExpoPushProvider:
    """Sends push notifications through the Expo Push Service.

    Uses httpx for async HTTP.  One or more batch requests are made when
    more than 100 messages are queued (_EXPO_CHUNK_SIZE).

    Per-message errors are captured as PushReceipt(status="error") so a
    single bad device never blocks delivery to other devices.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
        access_token: str | None = None,
    ) -> None:
        self._timeout = timeout_seconds
        self._access_token = access_token

    async def send_many(self, messages: list[PushMessage]) -> list[PushReceipt]:
        if not messages:
            return []

        receipts: list[PushReceipt] = []
        for chunk in _chunks(messages, _EXPO_CHUNK_SIZE):
            chunk_receipts = await self._send_chunk(chunk)
            receipts.extend(chunk_receipts)
        return receipts

    async def _send_chunk(self, messages: list[PushMessage]) -> list[PushReceipt]:
        payload = [_message_to_dict(m) for m in messages]
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    _EXPO_PUSH_URL,
                    json=payload,
                    headers=headers,
                )
        except httpx.TimeoutException as exc:
            raise ExpoNetworkError(
                f"Expo push request timed out after {self._timeout}s."
            ) from exc
        except httpx.RequestError as exc:
            raise ExpoNetworkError(
                f"Network error while contacting Expo: {exc}"
            ) from exc

        if response.status_code != 200:
            raise ExpoServiceError(
                f"Expo Push API returned HTTP {response.status_code}: {response.text[:200]}"
            )

        body = response.json()
        expo_data: list[dict] = body.get("data", [])

        if len(expo_data) != len(messages):
            # Defensive: Expo should always return one entry per message.
            logger.warning(
                "Expo returned %d receipts for %d messages; padding with errors.",
                len(expo_data),
                len(messages),
            )
            while len(expo_data) < len(messages):
                expo_data.append({"status": "error", "message": "missing receipt"})

        return [
            _parse_receipt(messages[i].to, expo_data[i])
            for i in range(len(messages))
        ]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _message_to_dict(msg: PushMessage) -> dict:
    return {
        "to": msg.to,
        "title": msg.title,
        "body": msg.body,
        "data": msg.data,
        "priority": msg.priority,
        "sound": getattr(msg, "sound", "default"),
        "channelId": getattr(msg, "channel_id", "default"),
    }


def _parse_receipt(token: str, entry: dict) -> PushReceipt:
    expo_status: str = entry.get("status", "error")

    if expo_status == "ok":
        return PushReceipt(
            token=token,
            status="ok",
            provider_id=entry.get("id"),
            failure_reason=None,
            is_invalid_token=False,
        )

    # status == "error"
    details: dict = entry.get("details", {})
    error_type: str | None = details.get("error")
    message: str = entry.get("message", "Unknown Expo error")
    is_invalid = error_type == _INVALID_TOKEN_REASON

    return PushReceipt(
        token=token,
        status="error",
        provider_id=None,
        failure_reason=f"{error_type}: {message}" if error_type else message,
        is_invalid_token=is_invalid,
    )


def _chunks(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i : i + size]
