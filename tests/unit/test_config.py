"""
Unit tests for core configuration.
"""
import pytest
from core.config import Settings


def test_settings_defaults():
    """Test that settings have sensible defaults."""
    # Create settings without environment variables
    settings = Settings(
        jwt_secret_key="test-secret",
        openai_api_key="test-key",
        supabase_url="https://test.supabase.co",
        supabase_key="test-key"
    )
    
    assert settings.app_name == "LEO Labor Law Chatbot"
    assert settings.environment == "development"
    assert settings.api_port == 8000
    assert settings.rate_limit_enabled is True


def test_cors_origins_parsing():
    """Test CORS origins can be parsed from comma-separated string."""
    settings = Settings(
        jwt_secret_key="test-secret",
        openai_api_key="test-key",
        supabase_url="https://test.supabase.co",
        supabase_key="test-key",
        cors_origins="http://localhost:3000,http://localhost:5173"
    )
    
    assert len(settings.cors_origins) == 2
    assert "http://localhost:3000" in settings.cors_origins


def test_temperature_validation():
    """Test that temperature is validated within range."""
    with pytest.raises(ValueError):
        Settings(
            jwt_secret_key="test-secret",
            openai_api_key="test-key",
            supabase_url="https://test.supabase.co",
            supabase_key="test-key",
            openai_temperature=3.0  # Invalid: > 2.0
        )
