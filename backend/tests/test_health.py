from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.fakes import FakeDatabaseManager


def test_health_reports_api_and_database_connected(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "application": "AgentTrace API",
        "api_status": "ok",
        "database_status": "connected",
    }


def test_health_reports_database_unavailable():
    with TestClient(create_app(database_manager=FakeDatabaseManager(connected=False))) as client:
        response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json()["database_status"] == "unavailable"


def test_health_reports_database_not_configured(client, manager):
    manager.client = None
    manager.database = None
    manager._connected = False
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json()["database_status"] == "not_configured"
    unavailable = client.get("/api/projects")
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "database_unavailable"


def test_real_application_starts_without_a_configured_database():
    settings = Settings(mongodb_uri=None)
    with TestClient(create_app(settings=settings)) as client:
        response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json() == {
        "application": "AgentTrace API",
        "api_status": "ok",
        "database_status": "not_configured",
    }
