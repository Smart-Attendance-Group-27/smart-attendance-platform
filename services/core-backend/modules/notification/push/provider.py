from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class PushMessage:
    """A single push notification to be delivered to one device token."""

    to: str            # Expo push token
    title: str
    body: str
    data: dict = field(default_factory=dict)
    priority: str = "default"   # "default" | "normal" | "high"
    sound: str = "default"
    channel_id: str = "default"


@dataclass(frozen=True)
class PushReceipt:
    """The result of attempting to deliver one PushMessage."""

    token: str
    status: str                  # "ok" | "error"
    provider_id: str | None      # Expo receipt ID when status == "ok"
    failure_reason: str | None   # Expo error detail when status == "error"
    is_invalid_token: bool       # True when Expo says DeviceNotRegistered


class PushProvider(Protocol):
    """Abstraction over a push-notification backend (Expo, FCM, APNs…).

    Implementations must not raise on per-message failures; they should
    return PushReceipt objects with status="error" instead, so that one
    bad device token does not prevent delivery to other devices.
    """

    async def send_many(self, messages: list[PushMessage]) -> list[PushReceipt]:
        """Send all messages and return one receipt per message, in order."""
        ...
