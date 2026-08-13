import pytest
from pydantic import ValidationError

from modules.attendance_sessions.qr_session.schemas import (
    DEFAULT_DYNAMIC_QR_REFRESH_INTERVAL_SECONDS,
    DEFAULT_QR_VALIDITY_SECONDS,
    MAX_QR_VALIDITY_SECONDS,
    MIN_QR_VALIDITY_SECONDS,
    CreateQrSessionRequest,
    VerifyQrSessionRequest,
)


def test_create_qr_session_request_uses_default_validity() -> None:
    payload = CreateQrSessionRequest()

    assert payload.mode == "static"
    assert payload.valid_for_seconds == DEFAULT_QR_VALIDITY_SECONDS
    assert payload.refresh_interval_seconds is None


def test_create_qr_session_request_accepts_camel_case_alias() -> None:
    payload = CreateQrSessionRequest(validForSeconds=MIN_QR_VALIDITY_SECONDS)

    assert payload.valid_for_seconds == MIN_QR_VALIDITY_SECONDS


def test_create_qr_session_request_accepts_explicit_static_mode() -> None:
    payload = CreateQrSessionRequest(mode="static", validForSeconds=300)

    assert payload.mode == "static"
    assert payload.refresh_interval_seconds is None


def test_create_qr_session_request_defaults_dynamic_refresh_interval() -> None:
    payload = CreateQrSessionRequest(mode="dynamic", validForSeconds=900)

    assert payload.mode == "dynamic"
    assert (
        payload.refresh_interval_seconds
        == DEFAULT_DYNAMIC_QR_REFRESH_INTERVAL_SECONDS
    )


def test_create_qr_session_request_accepts_dynamic_refresh_interval_alias() -> None:
    payload = CreateQrSessionRequest(
        mode="dynamic",
        validForSeconds=900,
        refreshIntervalSeconds=15,
    )

    assert payload.refresh_interval_seconds == 15


def test_create_qr_session_request_rejects_static_refresh_interval() -> None:
    with pytest.raises(ValidationError):
        CreateQrSessionRequest(
            mode="static",
            validForSeconds=300,
            refreshIntervalSeconds=15,
        )


def test_create_qr_session_request_rejects_invalid_mode() -> None:
    with pytest.raises(ValidationError):
        CreateQrSessionRequest(mode="rotating", validForSeconds=300)


@pytest.mark.parametrize(
    "valid_for_seconds",
    [MIN_QR_VALIDITY_SECONDS - 1, MAX_QR_VALIDITY_SECONDS + 1],
)
def test_create_qr_session_request_rejects_out_of_range_values(valid_for_seconds: int) -> None:
    with pytest.raises(ValidationError):
        CreateQrSessionRequest(validForSeconds=valid_for_seconds)


def test_verify_qr_session_request_accepts_camel_case_qr_value() -> None:
    payload = VerifyQrSessionRequest(qrValue="raw-test-token")

    assert payload.qr_value == "raw-test-token"


def test_verify_qr_session_request_rejects_empty_qr_value() -> None:
    with pytest.raises(ValidationError):
        VerifyQrSessionRequest(qrValue="")
