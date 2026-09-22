from fastapi.testclient import TestClient


def test_root_endpoint(client: TestClient):
    """Test the root endpoint returns 200 OK and expected keys."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "Mira"
    assert "version" in data
    assert data["docs"] == "/docs"
    assert data["health"] == "/health"


def test_root_health_endpoint(client: TestClient):
    """Test the root /health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app_name"] == "Mira"
    assert data["environment"] == "development"
    assert "version" in data


def test_api_v1_health_endpoint(client: TestClient):
    """Test the /api/v1/health endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app_name"] == "Mira"
    assert data["environment"] == "development"
    assert "version" in data
