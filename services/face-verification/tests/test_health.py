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
    )
    engine = MagicMock(spec=AsyncEngine)
    session_factory = object()
    face_engine = object()
    create_face_engine = MagicMock(return_value=face_engine)
    dispose_engine = AsyncMock()

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
        "create_insightface_engine",
        create_face_engine,
    )

    app = create_app()

    with TestClient(app):
        assert app.state.settings is settings
        assert app.state.db_engine is engine
        assert app.state.db_session_factory is session_factory
        assert app.state.face_engine is face_engine

    dispose_engine.assert_awaited_once_with(engine)
    create_face_engine.assert_called_once_with(
        model_name="buffalo_l",
        providers=("CPUExecutionProvider",),
        context_id=-1,
        detection_size=(640, 640),
        minimum_detection_confidence=0.60,
        max_concurrent_inferences=1,
    )
