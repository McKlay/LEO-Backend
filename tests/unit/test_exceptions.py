"""
Unit tests for exception handling.
"""
from fastapi import status
from core.exceptions import (
    AppError,
    ValidationError,
    RateLimitError,
    NotFoundError,
    format_error_response,
)


def test_app_error_basic():
    """Test basic AppError creation."""
    error = AppError("Test error")
    
    assert error.message == "Test error"
    assert error.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert error.error_code == "AppError"


def test_validation_error():
    """Test ValidationError has correct status code."""
    error = ValidationError("Invalid input")
    
    assert error.status_code == status.HTTP_400_BAD_REQUEST
    assert error.error_code == "VALIDATION_ERROR"


def test_rate_limit_error_with_retry():
    """Test RateLimitError includes retry_after."""
    error = RateLimitError(retry_after=60)
    
    assert error.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert error.details["retry_after"] == 60


def test_not_found_error():
    """Test NotFoundError formatting."""
    error = NotFoundError("Conversation", "conv-123")
    
    assert "Conversation not found: conv-123" in error.message
    assert error.status_code == status.HTTP_404_NOT_FOUND


def test_format_error_response():
    """Test error response formatting."""
    error = ValidationError("Invalid field", details={"field": "email"})
    response = format_error_response(error)
    
    assert response["error"]["code"] == "VALIDATION_ERROR"
    assert response["error"]["message"] == "Invalid field"
    assert response["error"]["details"]["field"] == "email"
