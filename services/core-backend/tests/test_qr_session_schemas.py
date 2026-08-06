import pytest
from pydantic import ValidationError

from modules.attendance_sessions.qr_session.schemas import (
    DEFAULT_QR_VALIDITY_SECONDS,
    MAX_QR_VALIDITY_SECONDS,
    MIN_QR_VALIDITY_SECONDS,
    CreateQrSessionRequest,
)


def test_create_qr_session_request_uses_default_validity() -> None:
    payload = CreateQrSessionRequest()

    assert payload.valid_for_seconds == DEFAULT_QR_VALIDITY_SECONDS


def test_create_qr_session_request_accepts_camel_case_alias() -> None:
    payload = CreateQrSessionRequest(validForSeconds=MIN_QR_VALIDITY_SECONDS)

    assert payload.valid_for_seconds == MIN_QR_VALIDITY_SECONDS


@pytest.mark.parametrize(
    "valid_for_seconds",
    [MIN_QR_VALIDITY_SECONDS - 1, MAX_QR_VALIDITY_SECONDS + 1],
)
def test_create_qr_session_request_rejects_out_of_range_values(valid_for_seconds: int) -> None:
    with pytest.raises(ValidationError):
        CreateQrSessionRequest(validForSeconds=valid_for_seconds)
