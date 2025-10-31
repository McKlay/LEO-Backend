"""
Custom exceptions and HTTP error mappings.

Defines domain-specific exceptions and their HTTP status code mappings
for consistent error handling across the application.
"""
from typing import Any, Optional
from fastapi import status


class AppError(Exception):
    """
    Base application exception.
    
    All custom exceptions should inherit from this class.
    """
    
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None
    ):
        """
        Initialize application error.
        
        Args:
            message: Error message
            status_code: HTTP status code
            error_code: Machine-readable error code
            details: Additional error details
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}


class ValidationError(AppError):
    """Raised when request validation fails."""
    
    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="VALIDATION_ERROR",
            details=details
        )


class AuthenticationError(AppError):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="AUTHENTICATION_ERROR"
        )


class AuthorizationError(AppError):
    """Raised when authorization fails."""
    
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="AUTHORIZATION_ERROR"
        )


class NotFoundError(AppError):
    """Raised when a requested resource is not found."""
    
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} not found: {identifier}",
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="NOT_FOUND"
        )


class ConflictError(AppError):
    """Raised when a resource conflict occurs."""
    
    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            error_code="CONFLICT"
        )


class RateLimitError(AppError):
    """Raised when rate limit is exceeded."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None
    ):
        details = {"retry_after": retry_after} if retry_after else {}
        super().__init__(
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code="RATE_LIMIT_EXCEEDED",
            details=details
        )


class ExternalServiceError(AppError):
    """Raised when an external service call fails."""
    
    def __init__(
        self,
        service: str,
        message: str = "External service error",
        details: Optional[dict[str, Any]] = None
    ):
        error_details = {"service": service}
        if details:
            error_details.update(details)
        
        super().__init__(
            message=f"{service}: {message}",
            status_code=status.HTTP_502_BAD_GATEWAY,
            error_code="EXTERNAL_SERVICE_ERROR",
            details=error_details
        )


class ModerationError(AppError):
    """Raised when content moderation fails."""
    
    def __init__(
        self,
        message: str = "Content violates usage policy",
        details: Optional[dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="CONTENT_MODERATION_FAILED",
            details=details
        )


class ConfigurationError(AppError):
    """Raised when application configuration is invalid."""
    
    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="CONFIGURATION_ERROR"
        )


class VectorStoreError(AppError):
    """Raised when vector store operations fail."""
    
    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(
            message=f"Vector store error: {message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="VECTOR_STORE_ERROR",
            details=details
        )


class LLMError(AppError):
    """Raised when LLM operations fail."""
    
    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(
            message=f"LLM error: {message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="LLM_ERROR",
            details=details
        )


class TranslationError(AppError):
    """Raised when translation operations fail."""
    
    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(
            message=f"Translation error: {message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="TRANSLATION_ERROR",
            details=details
        )


def format_error_response(error: AppError) -> dict[str, Any]:
    """
    Format application error as API response.
    
    Args:
        error: Application error instance
        
    Returns:
        Error response dictionary
    """
    response = {
        "error": {
            "code": error.error_code,
            "message": error.message,
        }
    }
    
    if error.details:
        response["error"]["details"] = error.details
    
    return response
