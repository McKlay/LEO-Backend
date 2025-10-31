"""
Session management service using Supabase anonymous authentication.

Handles session creation, token generation, and session validation.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from supabase import Client

from core import get_logger, AppError
from core.config import Settings

logger = get_logger(__name__)


class SessionService:
    """
    Service for managing anonymous user sessions with Supabase.
    
    Uses Supabase anonymous authentication for session management
    and JWT tokens for API authentication.
    """
    
    def __init__(self, supabase_client: Client, settings: Settings):
        """
        Initialize the session service.
        
        Args:
            supabase_client: Initialized Supabase client
            settings: Application settings
        """
        self.supabase = supabase_client
        self.settings = settings
        self.jwt_secret = settings.jwt_secret_key
        self.jwt_algorithm = settings.jwt_algorithm
        self.token_expiry_minutes = settings.jwt_access_token_expire_minutes
    
    async def create_anonymous_session(
        self,
        language: Optional[str] = "en",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new anonymous session using Supabase.
        
        Args:
            language: User's preferred language (en, fil, ceb)
            metadata: Optional session metadata
            
        Returns:
            Dict containing sessionId, token, and expiry information
            
        Raises:
            AppError: If session creation fails
        """
        try:
            # Sign in anonymously with Supabase
            auth_response = self.supabase.auth.sign_in_anonymously()
            
            if not auth_response or not auth_response.user:
                logger.error("Supabase anonymous sign-in failed: No user returned")
                raise AppError(
                    message="Failed to create anonymous session",
                    error_code="SESSION_CREATION_FAILED",
                    status_code=500
                )
            
            user = auth_response.user
            session = auth_response.session
            
            # Calculate token expiry
            expires_at = datetime.utcnow() + timedelta(minutes=self.token_expiry_minutes)
            
            # Create JWT payload with session information
            jwt_payload = {
                "sub": user.id,  # Subject (user ID)
                "session_id": session.access_token[:32] if session else user.id,  # Session identifier
                "language": language,
                "exp": expires_at,
                "iat": datetime.utcnow(),
                "type": "anonymous",
                "metadata": metadata or {}
            }
            
            # Generate our own JWT token for API authentication
            access_token = jwt.encode(
                jwt_payload,
                self.jwt_secret,
                algorithm=self.jwt_algorithm
            )
            
            logger.info(
                "Anonymous session created",
                extra={
                    "user_id": user.id,
                    "language": language,
                    "expires_at": expires_at.isoformat()
                }
            )
            
            return {
                "sessionId": user.id,
                "token": access_token,
                "expiresAt": expires_at.isoformat(),
                "expiresIn": self.token_expiry_minutes * 60,  # In seconds
                "language": language,
                "createdAt": datetime.utcnow().isoformat()
            }
            
        except JWTError as e:
            logger.error(f"JWT encoding error: {str(e)}")
            raise AppError(
                message="Failed to generate authentication token",
                error_code="TOKEN_GENERATION_FAILED",
                status_code=500
            )
        except Exception as e:
            logger.error(f"Session creation error: {str(e)}", exc_info=True)
            raise AppError(
                message="Failed to create session",
                error_code="SESSION_CREATION_FAILED",
                status_code=500,
                details={"error": str(e)}
            )
    
    async def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate a JWT token and extract session information.
        
        Args:
            token: JWT token to validate
            
        Returns:
            Dict containing decoded token payload
            
        Raises:
            AppError: If token is invalid or expired
        """
        try:
            # Decode and validate the JWT token
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=[self.jwt_algorithm]
            )
            
            # Check if token has expired
            exp_timestamp = payload.get("exp")
            if exp_timestamp:
                exp_datetime = datetime.fromtimestamp(exp_timestamp)
                if datetime.utcnow() > exp_datetime:
                    raise AppError(
                        message="Token has expired",
                        error_code="TOKEN_EXPIRED",
                        status_code=401
                    )
            
            return payload
            
        except JWTError as e:
            logger.warning(f"Invalid token: {str(e)}")
            raise AppError(
                message="Invalid authentication token",
                error_code="INVALID_TOKEN",
                status_code=401
            )
        except AppError:
            raise
        except Exception as e:
            logger.error(f"Token validation error: {str(e)}", exc_info=True)
            raise AppError(
                message="Token validation failed",
                error_code="TOKEN_VALIDATION_FAILED",
                status_code=401
            )
    
    async def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve session information from Supabase.
        
        Args:
            session_id: Session/user ID to retrieve
            
        Returns:
            Session information dict or None if not found
        """
        try:
            # Get user information from Supabase
            user = self.supabase.auth.admin.get_user_by_id(session_id)
            
            if user:
                return {
                    "sessionId": user.id,
                    "createdAt": user.created_at,
                    "lastSignInAt": user.last_sign_in_at,
                    "isAnonymous": user.is_anonymous
                }
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to retrieve session info: {str(e)}")
            return None
    
    async def refresh_session(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh an existing session using a refresh token.
        
        Args:
            refresh_token: Refresh token from previous session
            
        Returns:
            New session information with updated tokens
            
        Raises:
            AppError: If refresh fails
        """
        try:
            # Refresh the Supabase session
            auth_response = self.supabase.auth.refresh_session(refresh_token)
            
            if not auth_response or not auth_response.session:
                raise AppError(
                    message="Failed to refresh session",
                    error_code="SESSION_REFRESH_FAILED",
                    status_code=401
                )
            
            session = auth_response.session
            user = auth_response.user
            
            # Calculate new expiry
            expires_at = datetime.utcnow() + timedelta(minutes=self.token_expiry_minutes)
            
            # Create new JWT payload
            jwt_payload = {
                "sub": user.id,
                "session_id": session.access_token[:32],
                "exp": expires_at,
                "iat": datetime.utcnow(),
                "type": "anonymous"
            }
            
            # Generate new access token
            access_token = jwt.encode(
                jwt_payload,
                self.jwt_secret,
                algorithm=self.jwt_algorithm
            )
            
            logger.info(f"Session refreshed for user: {user.id}")
            
            return {
                "sessionId": user.id,
                "token": access_token,
                "expiresAt": expires_at.isoformat(),
                "expiresIn": self.token_expiry_minutes * 60,
                "refreshedAt": datetime.utcnow().isoformat()
            }
            
        except AppError:
            raise
        except Exception as e:
            logger.error(f"Session refresh error: {str(e)}", exc_info=True)
            raise AppError(
                message="Failed to refresh session",
                error_code="SESSION_REFRESH_FAILED",
                status_code=401
            )
