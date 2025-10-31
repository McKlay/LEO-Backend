"""
Integration tests for health check endpoints.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client."""
    from app.main import app
    return TestClient(app)


def test_health_check(client):
    """Test basic health check endpoint."""
    response = client.get("/api/v1/healthz")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "environment" in data


def test_readiness_check(client):
    """Test readiness check endpoint."""
    response = client.get("/api/v1/readyz")
    
    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    assert "checks" in data
    assert data["checks"]["app"] is True
