import asyncio
from uuid import uuid4

import httpx
import pytest

from adapters.core_api_student_profile_client import (
    CoreApiAdministratorRequiredError,
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


def test_requires_current_administrator_from_core_backend() -> None:
    user_id = uuid4()

    def handle_request(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/me"
        assert request.headers["authorization"] == "Bearer admin-token"
        return httpx.Response(
            200,
            json={"id": str(user_id), "roles": ["administrator"]},
        )

    client = CoreApiStudentProfileClient(
        base_url="http://core-api.test",
        timeout_seconds=5,
        transport=httpx.MockTransport(handle_request),
    )

    try:
        user = asyncio.run(client.require_current_administrator("admin-token"))
    finally:
        asyncio.run(client.close())

    assert user.id == user_id


def test_rejects_non_administrator_current_user() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"id": str(uuid4()), "roles": ["student"]},
        )
    )
    client = CoreApiStudentProfileClient(
        base_url="http://core-api.test",
        timeout_seconds=5,
        transport=transport,
    )

    try:
        with pytest.raises(CoreApiAdministratorRequiredError):
            asyncio.run(client.require_current_administrator("student-token"))
    finally:
        asyncio.run(client.close())

