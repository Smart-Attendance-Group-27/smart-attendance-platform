"""Unit tests for ExpoPushProvider."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import httpx

from modules.notification.push.expo_provider import ExpoPushProvider
from modules.notification.push.exception import ExpoNetworkError, ExpoServiceError
from modules.notification.push.provider import PushMessage

TOKEN_A = "ExponentPushToken[aaaaaaaaaaaaaaaaaaaaa]"
TOKEN_B = "ExponentPushToken[bbbbbbbbbbbbbbbbbbbbb]"


def make_message(to: str = TOKEN_A) -> PushMessage:
    return PushMessage(
        to=to,
        title="Test",
        body="Hello",
        data={},
        priority="default",
    )


def make_expo_ok_response(receipt_id: str = "receipt-1") -> dict:
    return {"data": [{"status": "ok", "id": receipt_id}]}


def make_expo_error_response(error: str = "DeviceNotRegistered", msg: str = "Not registered") -> dict:
    return {
        "data": [
            {
                "status": "error",
                "message": msg,
                "details": {"error": error},
            }
        ]
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_many_empty_returns_empty():
    provider = ExpoPushProvider()
    receipts = await provider.send_many([])
    assert receipts == []


@pytest.mark.asyncio
async def test_send_many_ok_receipt():
    provider = ExpoPushProvider()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = make_expo_ok_response("rid-001")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        receipts = await provider.send_many([make_message(TOKEN_A)])

    assert len(receipts) == 1
    r = receipts[0]
    assert r.status == "ok"
    assert r.provider_id == "rid-001"
    assert r.is_invalid_token is False
    assert r.token == TOKEN_A


@pytest.mark.asyncio
async def test_send_many_multiple_messages():
    provider = ExpoPushProvider()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {"status": "ok", "id": "rid-a"},
            {"status": "ok", "id": "rid-b"},
        ]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        receipts = await provider.send_many([make_message(TOKEN_A), make_message(TOKEN_B)])

    assert len(receipts) == 2
    assert all(r.status == "ok" for r in receipts)


# ---------------------------------------------------------------------------
# Error receipts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_device_not_registered_sets_is_invalid_token():
    provider = ExpoPushProvider()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = make_expo_error_response("DeviceNotRegistered")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        receipts = await provider.send_many([make_message(TOKEN_A)])

    r = receipts[0]
    assert r.status == "error"
    assert r.is_invalid_token is True


@pytest.mark.asyncio
async def test_other_expo_error_not_invalid_token():
    provider = ExpoPushProvider()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = make_expo_error_response("MessageRateExceeded")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        receipts = await provider.send_many([make_message(TOKEN_A)])

    r = receipts[0]
    assert r.status == "error"
    assert r.is_invalid_token is False


# ---------------------------------------------------------------------------
# Provider-level failures
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_200_response_raises_expo_service_error():
    provider = ExpoPushProvider()
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.text = "Too Many Requests"

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        with pytest.raises(ExpoServiceError):
            await provider.send_many([make_message(TOKEN_A)])


@pytest.mark.asyncio
async def test_timeout_raises_expo_network_error():
    provider = ExpoPushProvider(timeout_seconds=1.0)

    with patch(
        "httpx.AsyncClient.post",
        new_callable=AsyncMock,
        side_effect=httpx.TimeoutException("timed out"),
    ):
        with pytest.raises(ExpoNetworkError):
            await provider.send_many([make_message(TOKEN_A)])


@pytest.mark.asyncio
async def test_request_error_raises_expo_network_error():
    provider = ExpoPushProvider()

    with patch(
        "httpx.AsyncClient.post",
        new_callable=AsyncMock,
        side_effect=httpx.RequestError("connection refused"),
    ):
        with pytest.raises(ExpoNetworkError):
            await provider.send_many([make_message(TOKEN_A)])


# ---------------------------------------------------------------------------
# Batching
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sends_in_chunks_of_100():
    """201 messages should trigger 3 separate Expo requests (100+100+1)."""
    provider = ExpoPushProvider()
    messages = [make_message(f"ExponentPushToken[{'x' * 20}{i:03d}]") for i in range(201)]

    call_count = 0

    async def fake_post(url, *, json, headers, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"status": "ok", "id": f"r{i}"} for i in range(len(json))]
        }
        return mock_response

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=fake_post):
        receipts = await provider.send_many(messages)

    assert call_count == 3
    assert len(receipts) == 201


# ---------------------------------------------------------------------------
# Delivery receipts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_receipts_parses_delivered_and_invalid_token_results():
    provider = ExpoPushProvider()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "ticket-ok": {"status": "ok"},
            "ticket-dead": {
                "status": "error",
                "message": "The device is not registered",
                "details": {"error": "DeviceNotRegistered"},
            },
        }
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        receipts = await provider.fetch_receipts(["ticket-ok", "ticket-dead"])

    assert receipts["ticket-ok"].status == "ok"
    assert receipts["ticket-dead"].status == "error"
    assert receipts["ticket-dead"].is_invalid_token is True


@pytest.mark.asyncio
async def test_fetch_receipts_omits_ids_not_yet_available():
    provider = ExpoPushProvider()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {}}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        receipts = await provider.fetch_receipts(["ticket-pending"])

    assert receipts == {}


@pytest.mark.asyncio
async def test_fetch_receipts_uses_batches_of_1000():
    provider = ExpoPushProvider()
    provider_ids = [f"ticket-{index}" for index in range(2001)]
    batch_sizes: list[int] = []

    async def fake_post(url, *, json, headers, **kwargs):
        batch_sizes.append(len(json["ids"]))
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "data": {provider_id: {"status": "ok"} for provider_id in json["ids"]}
        }
        return response

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=fake_post):
        receipts = await provider.fetch_receipts(provider_ids)

    assert batch_sizes == [1000, 1000, 1]
    assert len(receipts) == 2001
