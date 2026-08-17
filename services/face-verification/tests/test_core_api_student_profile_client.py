import asyncio
from uuid import uuid4

import httpx
import pytest

from adapters.core_api_student_profile_client import (
    CoreApiForbiddenError,
    CoreApiStudentProfileClient,
    CoreApiStudentProfileNotFoundError,
    CoreApiUnauthorizedError,
    CoreApiUnavailableError,
)


def test_gets_current_student_profile_from_core_backend() -> None:
    student_id = uuid4()

    def handle_request(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/students/me/profile"
        assert request.headers["authorization"] == "Bearer signed-token"
        return httpx.Response(200, json={"id": str(student_id)})

    client = CoreApiStudentProfileClient(
        base_url="http://core-api.test",
        timeout_seconds=5,
        transport=httpx.MockTransport(handle_request),
    )

    try:
        profile = asyncio.run(
            client.get_current_student_profile("signed-token")
        )
    finally:
        asyncio.run(client.close())

    assert profile.id == student_id


@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (401, CoreApiUnauthorizedError),
        (403, CoreApiForbiddenError),
        (404, CoreApiStudentProfileNotFoundError),
        (500, CoreApiUnavailableError),
    ],
)
def test_maps_core_backend_failures(
    status_code: int,
    expected_error: type[Exception],
) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(status_code)
    )
    client = CoreApiStudentProfileClient(
        base_url="http://core-api.test",
        timeout_seconds=5,
        transport=transport,
    )

    try:
        with pytest.raises(expected_error):
            asyncio.run(
                client.get_current_student_profile("signed-token")
            )
    finally:
        asyncio.run(client.close())


def test_rejects_invalid_profile_response() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"id": "not-a-uuid"})
    )
    client = CoreApiStudentProfileClient(
        base_url="http://core-api.test",
        timeout_seconds=5,
        transport=transport,
    )

    try:
        with pytest.raises(CoreApiUnavailableError):
            asyncio.run(
                client.get_current_student_profile("signed-token")
            )
    finally:
        asyncio.run(client.close())

