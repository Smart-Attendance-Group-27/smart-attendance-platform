from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from modules.attendance_sessions.qr_session.crypto import (
    build_dynamic_qr_message,
    calculate_dynamic_qr_sequence,
    generate_dynamic_qr_value,
    get_dynamic_qr_window,
)


QR_SESSION_ID = UUID("50000000-0000-0000-0000-000000000001")
OTHER_QR_SESSION_ID = UUID("50000000-0000-0000-0000-000000000002")


def test_generate_dynamic_qr_value_is_deterministic_for_same_inputs() -> None:
    first_value = generate_dynamic_qr_value(QR_SESSION_ID, 17, "test-secret")
    second_value = generate_dynamic_qr_value(QR_SESSION_ID, 17, "test-secret")

    assert first_value == second_value
    assert "=" not in first_value


def test_generate_dynamic_qr_value_changes_for_different_sequence() -> None:
    first_value = generate_dynamic_qr_value(QR_SESSION_ID, 17, "test-secret")
    second_value = generate_dynamic_qr_value(QR_SESSION_ID, 18, "test-secret")

    assert first_value != second_value


def test_generate_dynamic_qr_value_changes_for_different_qr_session_id() -> None:
    first_value = generate_dynamic_qr_value(QR_SESSION_ID, 17, "test-secret")
    second_value = generate_dynamic_qr_value(OTHER_QR_SESSION_ID, 17, "test-secret")

    assert first_value != second_value


def test_generate_dynamic_qr_value_changes_for_different_secret() -> None:
    first_value = generate_dynamic_qr_value(QR_SESSION_ID, 17, "first-secret")
    second_value = generate_dynamic_qr_value(QR_SESSION_ID, 17, "second-secret")

    assert first_value != second_value


@pytest.mark.parametrize(
    ("now", "expected_sequence"),
    [
        (datetime(2026, 8, 6, 10, 0, 0, tzinfo=UTC), 0),
        (datetime(2026, 8, 6, 10, 0, 14, 999000, tzinfo=UTC), 0),
        (datetime(2026, 8, 6, 10, 0, 15, tzinfo=UTC), 1),
        (datetime(2026, 8, 6, 10, 0, 29, 999000, tzinfo=UTC), 1),
        (datetime(2026, 8, 6, 10, 0, 30, tzinfo=UTC), 2),
    ],
)
def test_calculate_dynamic_qr_sequence_uses_exact_slot_boundaries(
    now: datetime,
    expected_sequence: int,
) -> None:
    activated_at = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)

    assert calculate_dynamic_qr_sequence(activated_at, 15, now) == expected_sequence


def test_get_dynamic_qr_window_calculates_current_slot_times() -> None:
    activated_at = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)

    valid_from, expires_at = get_dynamic_qr_window(activated_at, 15, 17)

    assert valid_from == activated_at + timedelta(seconds=255)
    assert expires_at == activated_at + timedelta(seconds=270)


def test_calculate_dynamic_qr_sequence_rejects_invalid_refresh_interval() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        calculate_dynamic_qr_sequence(
            datetime(2026, 8, 6, 10, 0, tzinfo=UTC),
            0,
            datetime(2026, 8, 6, 10, 0, tzinfo=UTC),
        )


def test_calculate_dynamic_qr_sequence_rejects_now_before_activated_at() -> None:
    with pytest.raises(ValueError, match="before activated_at"):
        calculate_dynamic_qr_sequence(
            datetime(2026, 8, 6, 10, 0, tzinfo=UTC),
            15,
            datetime(2026, 8, 6, 9, 59, 59, tzinfo=UTC),
        )


def test_dynamic_qr_message_format_is_canonical() -> None:
    assert build_dynamic_qr_message(QR_SESSION_ID, 17) == (
        "qr:50000000-0000-0000-0000-000000000001:17"
    )
