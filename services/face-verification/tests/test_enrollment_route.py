import asyncio
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

import api.routes.enrollment as enrollment_route
from api.dependencies.admin import get_current_administrator_id
from api.routes.enrollment import stage_enrollment_uploads
from core.config import Settings
from main import create_app
from scripts.enroll_reference_faces import ImportSummary


def upload(filename: str, content: bytes, content_type: str = "image/jpeg") -> UploadFile:
    return UploadFile(
        filename=filename,
        file=BytesIO(content),
        headers=Headers({"content-type": content_type}),
    )


def test_stages_uploaded_images_in_temporary_directory(tmp_path: Path) -> None:
    images = [upload("230734J.jpg", b"photo"), upload("230735K.png", b"png", "image/png")]

    asyncio.run(stage_enrollment_uploads(images, tmp_path))

    assert (tmp_path / "230734J.jpg").read_bytes() == b"photo"
    assert (tmp_path / "230735K.png").read_bytes() == b"png"


@pytest.mark.parametrize("filename", ["../230734J.jpg", "folder/230734J.jpg", "folder\\230734J.jpg"])
def test_upload_rejects_unsafe_filenames(tmp_path: Path, filename: str) -> None:
    with pytest.raises(HTTPException) as error:
        asyncio.run(stage_enrollment_uploads([upload(filename, b"photo")], tmp_path))

    assert error.value.status_code == 400


def test_upload_rejects_unsupported_content_type(tmp_path: Path) -> None:
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            stage_enrollment_uploads(
                [upload("230734J.jpg", b"photo", "text/plain")],
                tmp_path,
            )
        )

    assert error.value.status_code == 415


def test_uploaded_source_images_are_deleted_after_enrolment(monkeypatch) -> None:
    staged_directory: Path | None = None

    async def fake_import_reference_photos(**kwargs):
        nonlocal staged_directory
        staged_directory = kwargs["photos_directory"]
        assert (staged_directory / "230734J.jpg").read_bytes() == b"photo"
        return ImportSummary(discovered=1, enrolled=1)

    monkeypatch.setattr(
        enrollment_route,
        "import_reference_photos",
        fake_import_reference_photos,
    )
    app = create_app(enable_database=False)
    app.state.settings = Settings(
        db_uri="postgresql://user:password@localhost:5432/postgres",
        face_embedding_encryption_key=(
            "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="
        ),
        _env_file=None,
    )
    app.state.db_session_factory = object()
    app.state.face_engine = object()
    app.state.reference_enrollment_lock = asyncio.Lock()
    app.dependency_overrides[get_current_administrator_id] = uuid4

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/internal/v1/reference-faces/enrolments/upload",
            files=[("images", ("230734J.jpg", b"photo", "image/jpeg"))],
        )

    assert response.status_code == 200
    assert response.json()["enrolled"] == 1
    assert staged_directory is not None
    assert not staged_directory.exists()
