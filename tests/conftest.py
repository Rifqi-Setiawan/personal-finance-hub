"""Pytest shared fixtures for Personal Finance Hub."""

import os
os.environ["FINANCE_HUB_DB_PATH"] = ":memory:"

import pytest
from fastapi.testclient import TestClient

from finance_hub.storage import StorageManager
from finance_hub.server import create_app
from finance_hub.parser.engine import ParserEngine


@pytest.fixture
def memory_storage():
    """Provides a fresh isolated in-memory DuckDB storage instance."""
    storage = StorageManager(db_path=":memory:")
    yield storage
    storage.close()


@pytest.fixture
def engine():
    """Provides a parser engine instance."""
    return ParserEngine()


@pytest.fixture
def client(memory_storage):
    """Provides a FastAPI TestClient wired to the in-memory storage."""
    app = create_app(storage_manager=memory_storage)
    with TestClient(app) as test_client:
        yield test_client
