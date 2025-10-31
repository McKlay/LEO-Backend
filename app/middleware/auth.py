"""
Authentication middleware for validating session tokens.
"""
from typing import Optional
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from core import get_logger, AppError
from services.auth import SessionService

logger = get_logger(__name__)

# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)


class AuthMiddleware:
    """
    Middleware for validating authentication tokens on protected endpoints.
    """
    
    def __init__(self, session_service: SessionService):
        """
        Initialize auth middleware.
        
        Args:
            session_service: Session service for token validation
        """
        self.session_service = session_service
    
    async def __call__(
        self,
        credentials: Optional[HTTPAuthorizationCredentials]
    ) -> dict:
        """
        Validate the bearer token and return session information.
        
        Args:
            credentials: HTTP authorization credentials
            
        Returns:
            Dict containing validated session payload
            
        Raises:
            HTTPException: If authentication fails
        """
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        token = credentials.credentials
        
        try:
            # Validate the token
            payload = await self.session_service.validate_token(token)
            return payload
            
        except AppError as e:
            logger.warning(f"Authentication failed: {e.message}")
            raise HTTPException(
                status_code=e.status_code,
                detail=e.message,
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception as e:
            logger.error(f"Unexpected auth error: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed",
                headers={"WWW-Authenticate": "Bearer"},
            )


async def get_current_session(
    credentials: HTTPAuthorizationCredentials = security,
    session_service: SessionService = None
) -> dict:
    """
    Dependency for getting current authenticated session.
    
    Use this as a FastAPI dependency on protected endpoints:
    
    ```python
    @router.get("/protected")
    async def protected_route(session: dict = Depends(get_current_session)):
        user_id = session["sub"]
        ...
    ```
    
    Args:
        credentials: HTTP Bearer token credentials
        session_service: Session service (injected via dependency)
        
    Returns:
        Validated session payload dict
        
    Raises:
        HTTPException: If authentication fails
    """
    if not session_service:
        from app.containers import get_session_service
        session_service = get_session_service()
    
    middleware = AuthMiddleware(session_service)
    return await middleware(credentials)
