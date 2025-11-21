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
        extra="ignore",
        json_file=None  # Don't try to parse env values as JSON
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
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        description="Allowed CORS origins (comma-separated)"
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
    openai_llm_model: str = Field(
        default="gpt-4.1",
        description="OpenAI chat model for pipeline response generation"
    )
    openai_ingestion_model: str = Field(
        default="gpt-4o",
        description="OpenAI model for KB ingestion (chunking, analysis)"
    )
    openai_embedding_model: str = Field(
        default="text-embedding-3-small",
        description="OpenAI embedding model"
    )
    llm_temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=2.0,
        description="LLM temperature for generation"
    )
    llm_max_tokens: int = Field(
        default=1000,
        gt=0,
        description="Maximum tokens for LLM responses"
    )
    enable_streaming: bool = Field(
        default=True,
        description="Enable streaming responses"
    )
    
    # Supabase Settings
    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_key: str = Field(..., description="Supabase service role key")
    supabase_db_url: Optional[str] = Field(
        default=None,
        description="Direct Postgres connection URL (optional)"
    )
    
    # Vector Store Settings
    vectorstore_table_name: str = Field(
        default="labor_law_sections",
        description="Vector store table name (new schema)"
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
    retrieval_similarity_threshold: float = Field(
        default=0.3,  # Lowered to 0.3 for better recall with small KB
        ge=0.0,
        le=1.0,
        description="Minimum similarity score for retrieval"
    )
    
    # Memory Settings
    memory_token_limit: int = Field(
        default=4000,
        gt=0,
        description="Maximum tokens to keep in memory"
    )
    max_history_messages: int = Field(
        default=10,
        gt=0,
        description="Maximum messages to keep in conversation history"
    )
    context_window_tokens: int = Field(
        default=4000,
        gt=0,
        description="Maximum tokens for context window"
    )
    
    # Grounding & Generation Settings
    max_context_length: int = Field(
        default=8000,
        gt=0,
        description="Maximum context length in characters"
    )
    enable_auto_disclaimer: bool = Field(
        default=True,
        description="Automatically add legal disclaimers"
    )
    enable_pii_redaction: bool = Field(
        default=False,
        description="Enable PII redaction in responses"
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
    
    # Query Analysis Settings
    enable_query_analysis: bool = Field(
        default=True,
        description="Enable LLM-based query analysis"
    )
    enable_smart_clarification: bool = Field(
        default=True,
        description="Enable smart clarification detection for vague queries"
    )
    query_analysis_model: str = Field(
        default="gpt-4o-mini",
        description="LLM model for query analysis"
    )
    analysis_timeout: float = Field(
        default=10.0,  # Increased from 5.0 to handle cold start latency
        gt=0.0,
        description="Timeout for query analysis in seconds"
    )
    max_clarification_questions: int = Field(
        default=4,
        ge=1,
        le=10,
        description="Maximum number of clarification questions to generate"
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
    enable_embedding_cache: bool = Field(
        default=True,
        description="Enable embedding caching to reduce API calls"
    )
    embedding_cache_size: int = Field(
        default=1000,
        gt=0,
        description="Maximum number of embeddings to cache (LRU)"
    )
    enable_connection_pooling: bool = Field(
        default=True,
        description="Enable database connection pooling"
    )
    db_pool_min_connections: int = Field(
        default=2,
        gt=0,
        description="Minimum database connections in pool"
    )
    db_pool_max_connections: int = Field(
        default=10,
        gt=0,
        description="Maximum database connections in pool"
    )
    
    def get_cors_origins(self) -> list[str]:
        """Get CORS origins as a list."""
        if isinstance(self.cors_origins, list):
            return self.cors_origins
        return [origin.strip() for origin in self.cors_origins.split(",")]


# Global settings instance
settings = Settings()
