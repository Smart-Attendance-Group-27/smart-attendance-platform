import base64
import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from uuid import UUID


DYNAMIC_QR_MESSAGE_PREFIX = "qr"


def calculate_dynamic_qr_sequence(
    activated_at: datetime,
    refresh_interval_seconds: int,
    now: datetime,
) -> int:
    # Sequence number is the dynamic QR "time bucket". For example, with a
    # 15-second refresh interval, every 15-second window gets a new sequence.
    activated_at_utc = _ensure_utc(activated_at)
    now_utc = _ensure_utc(now)

    if refresh_interval_seconds <= 0:
        raise ValueError("refresh_interval_seconds must be greater than zero.")

    elapsed_seconds = (now_utc - activated_at_utc).total_seconds()
    if elapsed_seconds < 0:
        raise ValueError("now must not be before activated_at.")

    return int(elapsed_seconds // refresh_interval_seconds)


def generate_dynamic_qr_value(
    qr_session_id: UUID,
    sequence: int,
    secret: str,
) -> str:
    # Dynamic QR values are deterministic for the backend but unpredictable to
    # clients because the message is signed with a server-side HMAC secret.
    if sequence < 0:
        raise ValueError("sequence must not be negative.")

    if not secret:
        raise ValueError("secret must not be empty.")

    message = build_dynamic_qr_message(qr_session_id, sequence)
    digest = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def get_dynamic_qr_window(
    activated_at: datetime,
    refresh_interval_seconds: int,
    sequence: int,
) -> tuple[datetime, datetime]:
    # The mobile verification result is only accepted inside this exact window.
    if refresh_interval_seconds <= 0:
        raise ValueError("refresh_interval_seconds must be greater than zero.")

    if sequence < 0:
        raise ValueError("sequence must not be negative.")

    activated_at_utc = _ensure_utc(activated_at)
    valid_from = activated_at_utc + timedelta(
        seconds=sequence * refresh_interval_seconds,
    )
    expires_at = valid_from + timedelta(seconds=refresh_interval_seconds)
    return valid_from, expires_at


def seconds_until_next_rotation(
    activated_at: datetime,
    refresh_interval_seconds: int,
    now: datetime,
) -> int:
    sequence = calculate_dynamic_qr_sequence(
        activated_at,
        refresh_interval_seconds,
        now,
    )
    _, expires_at = get_dynamic_qr_window(
        activated_at,
        refresh_interval_seconds,
        sequence,
    )
    remaining_seconds = (expires_at - _ensure_utc(now)).total_seconds()
    return max(0, int(remaining_seconds))


def build_dynamic_qr_message(qr_session_id: UUID, sequence: int) -> str:
    # Keep the signed message stable and explicit so web stream generation and
    # mobile verification always derive the same dynamic QR value.
    return f"{DYNAMIC_QR_MESSAGE_PREFIX}:{qr_session_id}:{sequence}"


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
