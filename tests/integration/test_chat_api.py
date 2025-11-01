"""
Integration tests for Phase 1.C - Chat API Implementation.

Tests the complete chat message flow including:
- Request validation
- Multi-turn conversation
- Rate limiting
- Error handling
- Citation and suggestion generation
"""
import pytest
import uuid
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from fastapi.testclient import TestClient
from app.main import create_app
from core import settings


@pytest.fixture
def test_app():
    """Create test FastAPI application."""
    app = create_app()
    return app


@pytest.fixture
def client(test_app):
    """Create test client."""
    return TestClient(test_app)


@pytest.fixture
def mock_session_token(client):
    """Create a valid session token for testing."""
    # Create anonymous session
    response = client.post(
        "/api/v1/auth/session",
        json={
            "preferredLanguage": "en",
            "deviceInfo": {
                "userAgent": "pytest",
                "timezone": "Asia/Manila"
            }
        }
    )
    assert response.status_code == 201
    data = response.json()
    return data["token"]


@pytest.fixture
def auth_headers(mock_session_token):
    """Get authorization headers with valid token."""
    return {"Authorization": f"Bearer {mock_session_token}"}


class TestChatMessageEndpoint:
    """Test chat message endpoint."""
    
    @pytest.mark.asyncio
    async def test_send_message_success(self, client, auth_headers):
        """Test successful chat message processing."""
        request_data = {
            "message": "What are my rights if I'm terminated without cause?",
            "language": "en"
        }
        
        with patch('services.chat_orchestrator.ChatOrchestrator.process_message') as mock_process:
            # Mock successful response
            mock_process.return_value = {
                "message_id": str(uuid.uuid4()),
                "conversation_id": str(uuid.uuid4()),
                "role": "assistant",
                "content": "Under Article 279 of the Labor Code...",
                "timestamp": datetime.utcnow(),
                "citations": [
                    {
                        "id": "cite-1",
                        "text": "Regular employees are entitled to security of tenure.",
                        "source": "Labor Code of the Philippines",
                        "article": "Article 279",
                        "url": "https://www.dole.gov.ph/labor-code/",
                        "confidence": 0.95
                    }
                ],
                "suggestions": [
                    {
                        "id": "action-1",
                        "type": "contact",
                        "label": "Contact DOLE",
                        "data": {
                            "name": "Department of Labor and Employment",
                            "hotline": "1349",
                            "email": "dolero4a@gmail.com",
                            "website": "https://www.dole.gov.ph"
                        }
                    }
                ],
                "metadata": {
                    "processing_time": 1.5,
                    "model": "gpt-4-turbo-preview",
                    "confidence": 0.92,
                    "disclaimer_required": True,
                    "tokens_used": 450
                }
            }
            
            response = client.post(
                "/api/v1/chat/message",
                json=request_data,
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Validate response schema
            assert "message_id" in data
            assert "conversation_id" in data
            assert "role" in data
            assert data["role"] == "assistant"
            assert "content" in data
            assert "timestamp" in data
            assert "citations" in data
            assert "suggestions" in data
            assert "metadata" in data
            
            # Validate citations
            assert len(data["citations"]) > 0
            citation = data["citations"][0]
            assert all(k in citation for k in ["id", "text", "source", "article", "url", "confidence"])
            
            # Validate suggestions
            assert len(data["suggestions"]) > 0
            suggestion = data["suggestions"][0]
            assert all(k in suggestion for k in ["id", "type", "label", "data"])
            
            # Validate metadata
            metadata = data["metadata"]
            assert all(k in metadata for k in ["processing_time", "model", "confidence", "disclaimer_required"])
    
    def test_send_message_with_conversation_id(self, client, auth_headers):
        """Test multi-turn conversation with existing conversation_id."""
        conversation_id = str(uuid.uuid4())
        
        with patch('services.chat_orchestrator.ChatOrchestrator.process_message') as mock_process:
            mock_process.return_value = {
                "message_id": str(uuid.uuid4()),
                "conversation_id": conversation_id,
                "role": "assistant",
                "content": "Follow-up response...",
                "timestamp": datetime.utcnow(),
                "citations": [],
                "suggestions": [],
                "metadata": {
                    "processing_time": 1.2,
                    "model": "gpt-4-turbo-preview",
                    "confidence": 0.88,
                    "disclaimer_required": True
                }
            }
            
            request_data = {
                "conversation_id": conversation_id,
                "message": "Can you clarify that?",
                "language": "en"
            }
            
            response = client.post(
                "/api/v1/chat/message",
                json=request_data,
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["conversation_id"] == conversation_id
    
    def test_send_message_validation_errors(self, client, auth_headers):
        """Test request validation errors."""
        # Test empty message
        response = client.post(
            "/api/v1/chat/message",
            json={"message": ""},
            headers=auth_headers
        )
        assert response.status_code == 422
        
        # Test message too long
        long_message = "x" * (settings.max_message_length + 1)
        response = client.post(
            "/api/v1/chat/message",
            json={"message": long_message},
            headers=auth_headers
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "VALIDATION_ERROR"
        
        # Test invalid language
        response = client.post(
            "/api/v1/chat/message",
            json={
                "message": "Test message",
                "language": "invalid"
            },
            headers=auth_headers
        )
        assert response.status_code == 422
    
    def test_send_message_multilingual(self, client, auth_headers):
        """Test multilingual message support."""
        languages = ["en", "fil", "ceb"]
        
        for lang in languages:
            with patch('services.chat_orchestrator.ChatOrchestrator.process_message') as mock_process:
                mock_process.return_value = {
                    "message_id": str(uuid.uuid4()),
                    "conversation_id": str(uuid.uuid4()),
                    "role": "assistant",
                    "content": f"Response in {lang}...",
                    "timestamp": datetime.utcnow(),
                    "citations": [],
                    "suggestions": [],
                    "metadata": {
                        "processing_time": 1.0,
                        "model": "gpt-4-turbo-preview",
                        "confidence": 0.9,
                        "disclaimer_required": True
                    }
                }
                
                response = client.post(
                    "/api/v1/chat/message",
                    json={
                        "message": "Test message",
                        "language": lang
                    },
                    headers=auth_headers
                )
                
                assert response.status_code == 200
    
    def test_send_message_unauthorized(self, client):
        """Test unauthorized access without token."""
        response = client.post(
            "/api/v1/chat/message",
            json={"message": "Test message"}
        )
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "UNAUTHORIZED"
    
    def test_send_message_with_context(self, client, auth_headers):
        """Test sending message with context metadata."""
        with patch('services.chat_orchestrator.ChatOrchestrator.process_message') as mock_process:
            mock_process.return_value = {
                "message_id": str(uuid.uuid4()),
                "conversation_id": str(uuid.uuid4()),
                "role": "assistant",
                "content": "Response...",
                "timestamp": datetime.utcnow(),
                "citations": [],
                "suggestions": [],
                "metadata": {
                    "processing_time": 1.0,
                    "model": "gpt-4-turbo-preview",
                    "confidence": 0.9,
                    "disclaimer_required": True
                }
            }
            
            request_data = {
                "message": "What about overtime?",
                "language": "en",
                "context": {
                    "previous_message_ids": ["msg-1", "msg-2"],
                    "user_metadata": {
                        "employment_type": "regular",
                        "industry": "IT"
                    }
                }
            }
            
            response = client.post(
                "/api/v1/chat/message",
                json=request_data,
                headers=auth_headers
            )
            
            assert response.status_code == 200


class TestRateLimiting:
    """Test rate limiting enforcement."""
    
    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self, client, auth_headers):
        """Test rate limiting kicks in after threshold."""
        # Disable rate limiting for this specific test initially
        original_setting = settings.rate_limit_enabled
        
        try:
            # Enable rate limiting
            settings.rate_limit_enabled = True
            
            with patch('services.chat_orchestrator.ChatOrchestrator.process_message') as mock_process:
                mock_process.return_value = {
                    "message_id": str(uuid.uuid4()),
                    "conversation_id": str(uuid.uuid4()),
                    "role": "assistant",
                    "content": "Response...",
                    "timestamp": datetime.utcnow(),
                    "citations": [],
                    "suggestions": [],
                    "metadata": {
                        "processing_time": 1.0,
                        "model": "gpt-4-turbo-preview",
                        "confidence": 0.9,
                        "disclaimer_required": True
                    }
                }
                
                # Send requests up to the limit
                for i in range(settings.rate_limit_chat_per_minute):
                    response = client.post(
                        "/api/v1/chat/message",
                        json={"message": f"Test message {i}"},
                        headers=auth_headers
                    )
                    
                    if response.status_code == 200:
                        # Check rate limit headers
                        assert "X-RateLimit-Limit" in response.headers
                        assert "X-RateLimit-Remaining" in response.headers
                        assert "X-RateLimit-Reset" in response.headers
                
                # Next request should be rate limited
                response = client.post(
                    "/api/v1/chat/message",
                    json={"message": "Rate limited message"},
                    headers=auth_headers
                )
                
                assert response.status_code == 429
                data = response.json()
                assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
                assert "retryAfter" in data["error"]
        
        finally:
            # Restore original setting
            settings.rate_limit_enabled = original_setting
    
    def test_rate_limit_headers(self, client, auth_headers):
        """Test rate limit headers are present in response."""
        if not settings.rate_limit_enabled:
            pytest.skip("Rate limiting not enabled")
        
        with patch('services.chat_orchestrator.ChatOrchestrator.process_message') as mock_process:
            mock_process.return_value = {
                "message_id": str(uuid.uuid4()),
                "conversation_id": str(uuid.uuid4()),
                "role": "assistant",
                "content": "Response...",
                "timestamp": datetime.utcnow(),
                "citations": [],
                "suggestions": [],
                "metadata": {
                    "processing_time": 1.0,
                    "model": "gpt-4-turbo-preview",
                    "confidence": 0.9,
                    "disclaimer_required": True
                }
            }
            
            response = client.post(
                "/api/v1/chat/message",
                json={"message": "Test message"},
                headers=auth_headers
            )
            
            if response.status_code == 200:
                assert "X-RateLimit-Limit" in response.headers
                assert "X-RateLimit-Remaining" in response.headers
                assert "X-RateLimit-Reset" in response.headers
                
                assert int(response.headers["X-RateLimit-Limit"]) == settings.rate_limit_chat_per_minute


class TestConversationClear:
    """Test conversation clearing endpoint."""
    
    @pytest.mark.asyncio
    async def test_clear_conversation_success(self, client, auth_headers):
        """Test successful conversation clearing."""
        conversation_id = str(uuid.uuid4())
        
        with patch('services.chat_orchestrator.ChatOrchestrator.clear_conversation') as mock_clear:
            mock_clear.return_value = None
            
            response = client.delete(
                f"/api/v1/chat/conversations/{conversation_id}",
                headers=auth_headers
            )
            
            assert response.status_code == 204
            mock_clear.assert_called_once_with(conversation_id)
    
    def test_clear_conversation_unauthorized(self, client):
        """Test unauthorized conversation clearing."""
        conversation_id = str(uuid.uuid4())
        
        response = client.delete(
            f"/api/v1/chat/conversations/{conversation_id}"
        )
        
        assert response.status_code == 401


class TestErrorHandling:
    """Test comprehensive error handling."""
    
    def test_processing_error(self, client, auth_headers):
        """Test handling of processing errors."""
        with patch('services.chat_orchestrator.ChatOrchestrator.process_message') as mock_process:
            mock_process.side_effect = Exception("Processing failed")
            
            response = client.post(
                "/api/v1/chat/message",
                json={"message": "Test message"},
                headers=auth_headers
            )
            
            assert response.status_code == 500
            data = response.json()
            assert "error" in data
            assert data["error"]["code"] == "INTERNAL_ERROR"
    
    def test_validation_error_format(self, client, auth_headers):
        """Test validation error response format."""
        response = client.post(
            "/api/v1/chat/message",
            json={"message": "x" * (settings.max_message_length + 1)},
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert "timestamp" in data["error"]
        assert data["error"]["code"] == "VALIDATION_ERROR"
