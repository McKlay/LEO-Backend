"""Core application configuration and utilities."""

from core.config import settings
from core.logging import setup_logging, get_logger, create_logger_with_context
from core.exceptions import (
    AppError,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ConflictError,
    RateLimitError,
    ExternalServiceError,
    ModerationError,
    ConfigurationError,
    VectorStoreError,
    LLMError,
    TranslationError,
    format_error_response,
)
from core.rate_limit import rate_limiter

__all__ = [
    # Configuration
    "settings",
    # Logging
    "setup_logging",
    "get_logger",
    "create_logger_with_context",
    # Exceptions
    "AppError",
    "ValidationError",
    "AuthenticationError",
    "AuthorizationError",
    "NotFoundError",
    "ConflictError",
    "RateLimitError",
    "ExternalServiceError",
    "ModerationError",
    "ConfigurationError",
    "VectorStoreError",
    "LLMError",
    "TranslationError",
    "format_error_response",
    # Rate Limiting
    "rate_limiter",
]
