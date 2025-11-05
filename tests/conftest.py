"""Test configuration and fixtures."""

import pytest
import os
import asyncio


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
