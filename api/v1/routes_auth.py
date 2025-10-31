"""
Authentication API endpoints.

Handles session creation and management.
"""
from typing import Optional
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from core import get_logger
from services.auth import SessionService
from app.containers import get_session_service

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# Request/Response Models
class CreateSessionRequest(BaseModel):
    """Request body for session creation."""
    
    language: Optional[str] = Field(
        default="en",
        description="User's preferred language",
        pattern="^(en|fil|ceb)$"
    )
    metadata: Optional[dict] = Field(
        default=None,
        description="Optional session metadata"
    )


class SessionResponse(BaseModel):
    """Response for session operations."""
    
    sessionId: str = Field(..., description="Unique session identifier")
    token: str = Field(..., description="JWT access token for authentication")
    expiresAt: str = Field(..., description="ISO 8601 timestamp when token expires")
    expiresIn: int = Field(..., description="Token lifetime in seconds")
    language: str = Field(..., description="Session language preference")
    createdAt: str = Field(..., description="ISO 8601 timestamp of session creation")


class RefreshSessionRequest(BaseModel):
    """Request body for session refresh."""
    
    refreshToken: str = Field(..., description="Refresh token from previous session")


# Endpoints
@router.post(
    "/session",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Anonymous Session",
    description="""
    Create a new anonymous session for chatbot interaction.
    
    Returns a JWT token that must be included in subsequent API requests
    via the Authorization header: `Authorization: Bearer <token>`
    
    Sessions expire after 7 days by default and can be used across
    multiple conversations.
    """
)
async def create_session(
    request: CreateSessionRequest,
    session_service: SessionService = Depends(get_session_service)
) -> SessionResponse:
    """
    Create a new anonymous session.
    
    Args:
        request: Session creation parameters
        session_service: Session service dependency
        
    Returns:
        Session information with authentication token
    """
    logger.info(
        "Creating anonymous session",
        extra={"language": request.language}
    )
    
    session_data = await session_service.create_anonymous_session(
        language=request.language,
        metadata=request.metadata
    )
    
    return SessionResponse(**session_data)


@router.post(
    "/session/refresh",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh Session",
    description="""
    Refresh an existing session to extend its lifetime.
    
    Provide a valid refresh token to obtain a new access token
    with extended expiration time.
    """
)
async def refresh_session(
    request: RefreshSessionRequest,
    session_service: SessionService = Depends(get_session_service)
) -> SessionResponse:
    """
    Refresh an existing session.
    
    Args:
        request: Refresh request with token
        session_service: Session service dependency
        
    Returns:
        New session information with refreshed token
    """
    logger.info("Refreshing session")
    
    session_data = await session_service.refresh_session(
        refresh_token=request.refreshToken
    )
    
    return SessionResponse(**session_data)
