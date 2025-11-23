"""Test configuration and fixtures."""

import pytest
import os
import asyncio
import json
from typing import Dict, Any
from httpx import Response


# Configure pytest-asyncio
pytest_plugins = ('pytest_asyncio',)


# Only set test environment variables if NOT running integration tests
if os.getenv("INTEGRATION_TEST", "false").lower() != "true":
    # Set test environment variables for unit tests
    os.environ["ENVIRONMENT"] = "development"
    os.environ["DEBUG"] = "true"
    os.environ["JWT_SECRET_KEY"] = "test-secret-key"
    os.environ["OPENAI_API_KEY"] = "test-openai-key"
    os.environ["SUPABASE_URL"] = "https://test.supabase.co"
    os.environ["SUPABASE_KEY"] = "test-supabase-key"
else:
    # Load real .env for integration tests
    from dotenv import load_dotenv
    load_dotenv()


async def parse_sse_response(response: Response) -> Dict[str, Any]:
    """
    Parse Server-Sent Events (SSE) response from streaming endpoint.
    
    Utility function for tests to consume streaming responses and convert
    them to the same format as the old non-streaming endpoint.
    
    Args:
        response: HTTPX Response object from streaming endpoint
        
    Returns:
        Dict with keys: messageId, content, citations, suggestions, metadata
    """
    content_chunks = []
    citations = []
    suggestions = []
    metadata = {}
    message_id = None
    current_event_type = None
    
    # Read response stream
    async for line in response.aiter_lines():
        line = line.strip()
        if not line:
            continue
            
        # Parse SSE format
        if line.startswith('event: '):
            current_event_type = line[7:].strip()
        elif line.startswith('data: '):
            data_str = line[6:].strip()
            
            if data_str == '[DONE]':
                continue
                
            try:
                event_data = json.loads(data_str)
                
                # Handle different event types
                if current_event_type == 'content_chunk':
                    content_chunks.append(event_data.get('chunk', ''))
                elif current_event_type == 'citations':
                    citations = event_data.get('citations', event_data)
                elif current_event_type == 'complete':
                    # Complete event contains all final data
                    if 'content' in event_data and not content_chunks:
                        content_chunks.append(event_data['content'])
                    if 'citations' in event_data and not citations:
                        citations = event_data['citations']
                    if 'suggestions' in event_data:
                        suggestions = event_data['suggestions']
                    if 'metadata' in event_data:
                        metadata = event_data['metadata']
                    if 'messageId' in event_data:
                        message_id = event_data['messageId']
                elif current_event_type == 'metadata':
                    metadata.update(event_data)
                    if 'messageId' in event_data:
                        message_id = event_data['messageId']
                # Ignore 'status' events in tests
                
                current_event_type = None
            except json.JSONDecodeError:
                continue
    
    # Combine content chunks
    full_content = ''.join(content_chunks)
    
    return {
        'messageId': message_id or 'test-message-id',
        'content': full_content,
        'citations': citations,
        'suggestions': suggestions,
        'metadata': metadata
    }


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the entire test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings():
    """Provide mock settings for tests."""
    from core.config import Settings
    
    return Settings(
        jwt_secret_key="test-secret",
        openai_api_key="test-key",
        supabase_url="https://test.supabase.co",
        supabase_key="test-key",
        debug=True,
        environment="development"
    )
