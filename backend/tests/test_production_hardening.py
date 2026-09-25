import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.app.main import app, create_application
from backend.app.core.config import Settings, settings
from backend.app.core.database import get_db
from backend.app.models.base import Base


@pytest.fixture
def test_db():
    """Create a fresh in-memory SQLite database for each test."""
    db_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(db_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(db_engine)


@pytest.fixture
def client(test_db: Session):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_liveness_endpoints(client: TestClient):
    """Verify liveness probe returns ok on both root and api/v1."""
    # Root /health
    root_resp = client.get("/health")
    assert root_resp.status_code == 200
    assert root_resp.json()["status"] == "ok"
    assert root_resp.json()["version"] == "1.0.0"

    # API v1 /api/v1/health
    v1_resp = client.get("/api/v1/health")
    assert v1_resp.status_code == 200
    assert v1_resp.json()["status"] == "ok"
    assert v1_resp.json()["version"] == "1.0.0"


def test_readiness_endpoints(client: TestClient):
    """Verify readiness probe verifies database connectivity on both root and api/v1."""
    # Root /ready
    root_ready = client.get("/ready")
    assert root_ready.status_code == 200
    assert root_ready.json()["status"] == "ok"
    assert root_ready.json()["database"] == "connected"

    # API v1 /api/v1/ready
    v1_ready = client.get("/api/v1/ready")
    assert v1_ready.status_code == 200
    assert v1_ready.json()["status"] == "ok"
    assert v1_ready.json()["database"] == "connected"


def test_security_headers_injected(client: TestClient):
    """Verify standard security headers are injected by middleware."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "geolocation=()" in resp.headers.get("Permissions-Policy", "")


def test_root_metadata_endpoint(client: TestClient):
    """Verify root endpoint returns basic application information."""
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["app"] == "Mira"
    assert data["version"] == "1.0.0"
    assert "health" in data
    assert "ready" in data


def test_production_environment_defaults():
    """Verify production settings defaults disable debug and docs by default.

    The .env file sets DEBUG=True and ENABLE_DOCS=True for local development.
    This test explicitly overrides DEBUG=None and ENABLE_DOCS=None so the
    model_validator's environment-inference logic is exercised directly,
    independent of .env file values.
    """
    # Pass DEBUG=None and ENABLE_DOCS=None to bypass .env file overrides
    # and let the model_validator compute the correct production defaults.
    prod_settings = Settings(ENVIRONMENT="production", DEBUG=None, ENABLE_DOCS=None, LOG_LEVEL="INFO")
    assert prod_settings.DEBUG is False
    assert prod_settings.ENABLE_DOCS is False
    assert prod_settings.LOG_LEVEL == "INFO"

    dev_settings = Settings(ENVIRONMENT="development", DEBUG=None, ENABLE_DOCS=None)
    assert dev_settings.DEBUG is True
    assert dev_settings.ENABLE_DOCS is True


def test_cors_origins_parsing():
    """Verify comma-separated CORS origins string parses into clean list."""
    s = Settings(CORS_ORIGINS="https://mira.app, https://api.mira.app")
    assert s.CORS_ORIGINS == ["https://mira.app", "https://api.mira.app"]


def test_global_exception_handler_sanitizes_in_production(monkeypatch):
    """Verify unhandled exceptions in production do not expose tracebacks to client."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    test_app = create_application()

    @test_app.get("/test-internal-error")
    def trigger_error():
        raise RuntimeError("Sensitive DB Connection string with password inside")

    with TestClient(test_app, raise_server_exceptions=False) as c:
        resp = c.get("/test-internal-error")
        assert resp.status_code == 500
        data = resp.json()
        assert "password" not in data["detail"].lower()
        assert "internal server error occurred" in data["detail"].lower()
