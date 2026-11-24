import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.main import create_app  # noqa: E402
from tests.fakes import FakeDatabaseManager  # noqa: E402


@pytest.fixture
def manager() -> FakeDatabaseManager:
    return FakeDatabaseManager()


@pytest.fixture
def client(manager: FakeDatabaseManager):
    with TestClient(create_app(database_manager=manager)) as test_client:
        yield test_client


@pytest.fixture
def database(manager: FakeDatabaseManager):
    return manager.database
