"""
Core configuration module using Pydantic Settings.

Loads environment variables and provides validated configuration
for all application components.
"""
from typing import Literal, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application Settings
    app_name: str = Field(default="LEO Labor Law Chatbot", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Current environment"
    )
    debug: bool = Field(default=False, description="Debug mode")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level"
    )
    
    # API Settings
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    api_prefix: str = Field(default="/api", description="API route prefix")
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins"
    )
    
    # Security Settings
    jwt_secret_key: str = Field(..., description="JWT secret key for token signing")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_access_token_expire_minutes: int = Field(
        default=60 * 24 * 7,  # 7 days
        description="JWT access token expiration in minutes"
    )
    
    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_chat_per_minute: int = Field(
        default=10,
        description="Chat requests per minute per session"
    )
    rate_limit_conversations_per_minute: int = Field(
        default=100,
        description="Conversation API requests per minute per session"
    )
    
    # OpenAI Settings
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_model: str = Field(
        default="gpt-4.1",
        description="OpenAI chat model"
    )
    openai_embedding_model: str = Field(
        default="text-embedding-3-small",
        description="OpenAI embedding model"
    )
    openai_temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=2.0,
        description="LLM temperature for generation"
    )
    openai_max_tokens: int = Field(
        default=2000,
        gt=0,
        description="Maximum tokens for LLM responses"
    )
    
    # Supabase Settings
    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_key: str = Field(..., description="Supabase service role key")
    supabase_db_url: Optional[str] = Field(
        default=None,
        description="Direct Postgres connection URL (optional)"
    )
    
    # Vector Store Settings
    vector_table_name: str = Field(
        default="labor_law_embeddings",
        description="Vector store table name"
    )
    embedding_dimension: int = Field(
        default=1536,
        description="Embedding vector dimension"
    )
    retrieval_top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of chunks to retrieve"
    )
    
    # Google Cloud Settings (Optional - Translation & Maps)
    enable_translation: bool = Field(
        default=False,
        description="Enable Google Cloud Translation"
    )
    google_cloud_project_id: Optional[str] = Field(
        default=None,
        description="Google Cloud project ID"
    )
    google_translate_api_key: Optional[str] = Field(
        default=None,
        description="Google Cloud Translation API key"
    )
    google_maps_api_key: Optional[str] = Field(
        default=None,
        description="Google Maps Places API key"
    )
    
    # NLP Settings
    enable_intent_classification: bool = Field(
        default=True,
        description="Enable intent classification for retrieval"
    )
    intent_confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence for intent-based filtering"
    )
    
    # Chat Settings
    max_message_length: int = Field(
        default=2000,
        gt=0,
        description="Maximum user message length in characters"
    )
    max_conversation_history: int = Field(
        default=10,
        gt=0,
        description="Maximum messages to keep in conversation memory"
    )
    
    # Moderation Settings
    enable_moderation: bool = Field(
        default=True,
        description="Enable content moderation"
    )
    moderation_fail_on_violation: bool = Field(
        default=True,
        description="Reject requests that violate content policy"
    )
    
    # Performance Settings
    enable_caching: bool = Field(
        default=True,
        description="Enable response caching"
    )
    cache_ttl_seconds: int = Field(
        default=3600,
        gt=0,
        description="Cache time-to-live in seconds"
    )
    
    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


# Global settings instance
settings = Settings()
