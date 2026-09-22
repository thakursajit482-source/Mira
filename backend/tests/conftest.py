import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Test client fixture for making synchronous test requests to the FastAPI application."""
    with TestClient(app) as test_client:
        yield test_client
