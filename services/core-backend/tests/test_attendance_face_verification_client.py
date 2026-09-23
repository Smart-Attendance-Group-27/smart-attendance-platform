from unittest.mock import AsyncMock, patch
from uuid import UUID

import httpx
import pytest

from modules.attendance_verification.face.client import (
    FaceVerificationServiceClient,
)


SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
DOWNSTREAM_URL = (
    "http://face-verification:8001/internal/v1/attendance-sessions/"
    f"{SESSION_ID}/face-verifications"
)
LIVENESS_JSON = (
    '{"version":1,"method":"mlkit_challenge","passed":true,'
    '"challenges":["turn_left","eyes_closed_hold"],'
    '"startedAt":"2026-09-22T08:00:00Z",'
    '"completedAt":"2026-09-22T08:00:10Z",'
    '"engine":"uniattend-mobile-liveness"}'
)


def successful_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={"status": "passed", "attemptNumber": 1, "canRetry": False},
    )


@pytest.mark.asyncio
async def test_forwards_image_and_liveness_opaquely() -> None:
    client = FaceVerificationServiceClient(
        base_url="http://face-verification:8001",
        timeout_seconds=30,
    )

    with patch(
        "modules.attendance_verification.face.client.httpx.AsyncClient.post",
        new_callable=AsyncMock,
        return_value=successful_response(),
    ) as post:
        result = await client.verify_attendance_face(
            session_id=SESSION_ID,
            access_token="student-token",
            image=b"original-image-bytes",
            content_type="image/png",
            liveness=LIVENESS_JSON,
        )

    assert result.status == "passed"
    post.assert_awaited_once_with(
        DOWNSTREAM_URL,
        headers={"Authorization": "Bearer student-token"},
        files={
            "image": (
                "capture.jpg",
                b"original-image-bytes",
                "image/png",
            )
        },
        data={"liveness": LIVENESS_JSON},
    )


@pytest.mark.asyncio
async def test_preserves_missing_liveness_for_downstream_enforcement() -> None:
    client = FaceVerificationServiceClient(
        base_url="http://face-verification:8001",
        timeout_seconds=30,
    )

    with patch(
        "modules.attendance_verification.face.client.httpx.AsyncClient.post",
        new_callable=AsyncMock,
        return_value=successful_response(),
    ) as post:
        await client.verify_attendance_face(
            session_id=SESSION_ID,
            access_token="student-token",
            image=b"original-image-bytes",
            content_type="image/jpeg",
            liveness=None,
        )

    post.assert_awaited_once_with(
        DOWNSTREAM_URL,
        headers={"Authorization": "Bearer student-token"},
        files={
            "image": (
                "capture.jpg",
                b"original-image-bytes",
                "image/jpeg",
            )
        },
        data=None,
    )
