from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine

import main
from main import create_app


def test_health_endpoint() -> None:
    app = create_app(enable_database=False)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "face-verification",
    }


def test_lifespan_creates_and_disposes_database_resources(
    monkeypatch,
) -> None:
    settings = SimpleNamespace(
        face_model_name="buffalo_l",
        face_model_version="1",
        face_execution_provider="CPUExecutionProvider",
        face_context_id=-1,
        face_detection_size=640,
        face_minimum_detection_confidence=0.60,
        face_max_concurrent_inferences=1,
        core_api_url="http://localhost:8000",
        core_api_timeout_seconds=5,
    )
    engine = MagicMock(spec=AsyncEngine)
    session_factory = object()
    face_engine = object()
    create_face_engine = MagicMock(return_value=face_engine)
    dispose_engine = AsyncMock()
    core_api_client = MagicMock()
    core_api_client.close = AsyncMock()
    create_core_api_client = MagicMock(return_value=core_api_client)

    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(
        main,
        "create_database_engine",
        lambda configured_settings: engine,
    )
    monkeypatch.setattr(
        main,
        "create_session_factory",
        lambda configured_engine: session_factory,
    )
    monkeypatch.setattr(main, "dispose_database_engine", dispose_engine)
    monkeypatch.setattr(
        main,
        "CoreApiStudentProfileClient",
        create_core_api_client,
    )
    monkeypatch.setattr(
        main,
        "create_configured_insightface_engine",
        create_face_engine,
    )

    app = create_app()

    with TestClient(app):
        assert app.state.settings is settings
        assert app.state.db_engine is engine
        assert app.state.db_session_factory is session_factory
        assert app.state.core_api_student_profile_client is core_api_client
        assert app.state.face_engine is face_engine

    core_api_client.close.assert_awaited_once_with()
    dispose_engine.assert_awaited_once_with(engine)
    create_core_api_client.assert_called_once_with(
        base_url="http://localhost:8000",
        timeout_seconds=5,
    )
    create_face_engine.assert_called_once_with(settings)
