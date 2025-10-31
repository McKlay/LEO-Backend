"""Test configuration and fixtures."""

import pytest
import os


# Set test environment variables
os.environ["ENVIRONMENT"] = "development"
os.environ["DEBUG"] = "true"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"
os.environ["OPENAI_API_KEY"] = "test-openai-key"
os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_KEY"] = "test-supabase-key"


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
