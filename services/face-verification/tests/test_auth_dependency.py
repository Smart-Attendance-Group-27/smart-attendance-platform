import asyncio
from typing import Annotated
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from adapters.core_api_student_profile_client import (
    CoreApiStudentProfileClient,
)
from api.dependencies.auth import get_current_student_id


def create_test_app(
    status_code: int,
    response_body: dict[str, str] | None = None,
) -> tuple[FastAPI, CoreApiStudentProfileClient]:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(status_code, json=response_body)
    )
    core_api_client = CoreApiStudentProfileClient(
        base_url="http://core-api.test",
        timeout_seconds=5,
        transport=transport,
    )
    app = FastAPI()
    app.state.core_api_student_profile_client = core_api_client

    @app.get("/student-id")
    async def read_student_id(
        student_id: Annotated[UUID, Depends(get_current_student_id)],
    ) -> dict[str, str]:
        return {"student_id": str(student_id)}

    return app, core_api_client


def test_returns_profile_id_resolved_by_core_backend() -> None:
    student_id = uuid4()
    app, core_api_client = create_test_app(
        200,
        {"id": str(student_id)},
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                "/student-id",
                headers={"Authorization": "Bearer signed-token"},
            )
    finally:
        asyncio.run(core_api_client.close())

    assert response.status_code == 200
    assert response.json() == {"student_id": str(student_id)}


def test_requires_bearer_access_token() -> None:
    app, core_api_client = create_test_app(500)

    try:
        with TestClient(app) as client:
            response = client.get("/student-id")
    finally:
        asyncio.run(core_api_client.close())

    assert response.status_code == 401
    assert response.json() == {
        "detail": "A bearer access token is required.",
    }
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    ("core_status", "expected_status", "expected_detail"),
    [
        (401, 401, "Access token is not valid."),
        (403, 403, "The 'student' role is required."),
        (404, 404, "No active student profile exists for this account."),
        (
            500,
            503,
            "Could not resolve the student through the Core Backend.",
        ),
    ],
)
def test_maps_core_profile_errors_to_safe_http_responses(
    core_status: int,
    expected_status: int,
    expected_detail: str,
) -> None:
    app, core_api_client = create_test_app(core_status)

    try:
        with TestClient(app) as client:
            response = client.get(
                "/student-id",
                headers={"Authorization": "Bearer signed-token"},
            )
    finally:
        asyncio.run(core_api_client.close())

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}

