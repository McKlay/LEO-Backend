"""
Integration tests for authentication endpoints.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timedelta

from app.main import app


class TestAuthenticationEndpoints:
    """Test suite for authentication API endpoints."""
    
    @pytest.mark.asyncio
    async def test_create_anonymous_session_success(self):
        """Test successful anonymous session creation."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/session",
                json={"language": "en"}
            )
            
            assert response.status_code == 201
            data = response.json()
            
            # Verify response structure
            assert "sessionId" in data
            assert "token" in data
            assert "expiresAt" in data
            assert "expiresIn" in data
            assert "language" in data
            assert "createdAt" in data
            
            # Verify data types and values
            assert isinstance(data["sessionId"], str)
            assert len(data["sessionId"]) > 0
            assert isinstance(data["token"], str)
            assert len(data["token"]) > 0
            assert data["language"] == "en"
            assert data["expiresIn"] > 0
            
            # Verify timestamps are valid ISO 8601
            datetime.fromisoformat(data["expiresAt"].replace("Z", "+00:00"))
            datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00"))
    
    @pytest.mark.asyncio
    async def test_create_session_with_filipino_language(self):
        """Test session creation with Filipino language preference."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/session",
                json={"language": "fil"}
            )
            
            assert response.status_code == 201
            data = response.json()
            assert data["language"] == "fil"
    
    @pytest.mark.asyncio
    async def test_create_session_with_cebuano_language(self):
        """Test session creation with Cebuano language preference."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/session",
                json={"language": "ceb"}
            )
            
            assert response.status_code == 201
            data = response.json()
            assert data["language"] == "ceb"
    
    @pytest.mark.asyncio
    async def test_create_session_with_metadata(self):
        """Test session creation with custom metadata."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            metadata = {
                "userAgent": "Mozilla/5.0",
                "platform": "web"
            }
            
            response = await client.post(
                "/api/v1/auth/session",
                json={
                    "language": "en",
                    "metadata": metadata
                }
            )
            
            assert response.status_code == 201
            data = response.json()
            assert data["sessionId"] is not None
    
    @pytest.mark.asyncio
    async def test_create_session_default_language(self):
        """Test session creation with default language (en)."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/session",
                json={}
            )
            
            assert response.status_code == 201
            data = response.json()
            assert data["language"] == "en"
    
    @pytest.mark.asyncio
    async def test_create_session_invalid_language(self):
        """Test session creation with invalid language code."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/session",
                json={"language": "invalid"}
            )
            
            # Should fail validation
            assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_token_format_is_jwt(self):
        """Test that returned token is a valid JWT format."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/session",
                json={"language": "en"}
            )
            
            assert response.status_code == 201
            data = response.json()
            token = data["token"]
            
            # JWT tokens have 3 parts separated by dots
            parts = token.split(".")
            assert len(parts) == 3
    
    @pytest.mark.asyncio
    async def test_multiple_session_creation(self):
        """Test creating multiple sessions returns unique tokens."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Create first session
            response1 = await client.post(
                "/api/v1/auth/session",
                json={"language": "en"}
            )
            
            # Create second session
            response2 = await client.post(
                "/api/v1/auth/session",
                json={"language": "en"}
            )
            
            assert response1.status_code == 201
            assert response2.status_code == 201
            
            data1 = response1.json()
            data2 = response2.json()
            
            # Sessions should be different
            assert data1["sessionId"] != data2["sessionId"]
            assert data1["token"] != data2["token"]
    
    @pytest.mark.asyncio
    async def test_session_expiry_time(self):
        """Test that session expiry is set correctly."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/session",
                json={"language": "en"}
            )
            
            assert response.status_code == 201
            data = response.json()
            
            created_at = datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00"))
            expires_at = datetime.fromisoformat(data["expiresAt"].replace("Z", "+00:00"))
            
            # Check that expiry is in the future
            assert expires_at > created_at
            
            # Check that expiry is approximately 7 days (default)
            expected_expiry = created_at + timedelta(days=7)
            time_diff = abs((expires_at - expected_expiry).total_seconds())
            
            # Allow 1 minute tolerance
            assert time_diff < 60


class TestSessionValidation:
    """Test suite for session token validation."""
    
    @pytest.mark.asyncio
    async def test_protected_endpoint_without_token(self):
        """Test accessing protected endpoint without authentication."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # This will be tested once we have protected endpoints
            # For now, just verify the auth middleware exists
            pass
    
    @pytest.mark.asyncio
    async def test_protected_endpoint_with_valid_token(self):
        """Test accessing protected endpoint with valid token."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Create session
            auth_response = await client.post(
                "/api/v1/auth/session",
                json={"language": "en"}
            )
            
            assert auth_response.status_code == 201
            token = auth_response.json()["token"]
            
            # Token should be valid JWT
            assert len(token.split(".")) == 3
    
    @pytest.mark.asyncio
    async def test_invalid_token_format(self):
        """Test that invalid token format is rejected."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # This will be tested once we have protected endpoints
            # that use the auth middleware
            pass


class TestSessionMetadata:
    """Test suite for session metadata and properties."""
    
    @pytest.mark.asyncio
    async def test_session_response_contains_all_fields(self):
        """Test that session response contains all required fields."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/session",
                json={"language": "en"}
            )
            
            assert response.status_code == 201
            data = response.json()
            
            required_fields = [
                "sessionId",
                "token",
                "expiresAt",
                "expiresIn",
                "language",
                "createdAt"
            ]
            
            for field in required_fields:
                assert field in data, f"Missing required field: {field}"
    
    @pytest.mark.asyncio
    async def test_expires_in_matches_calculation(self):
        """Test that expiresIn seconds matches the timestamp difference."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/session",
                json={"language": "en"}
            )
            
            assert response.status_code == 201
            data = response.json()
            
            created_at = datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00"))
            expires_at = datetime.fromisoformat(data["expiresAt"].replace("Z", "+00:00"))
            expires_in = data["expiresIn"]
            
            # Calculate expected seconds
            expected_seconds = (expires_at - created_at).total_seconds()
            
            # Allow small tolerance for execution time
            assert abs(expires_in - expected_seconds) < 2
