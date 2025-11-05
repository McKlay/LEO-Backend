"""
Chat API routes.

Implements POST /api/chat/message endpoint for processing chat messages.
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse

from core import get_logger, AppError, settings
from core.exceptions import RateLimitError, ValidationError
from core.rate_limit import rate_limiter
from api.v1.schemas_chat import ChatMessageRequest, ChatMessageResponse
from app.containers import get_chat_orchestrator
from app.middleware.auth import get_current_session
from services.chat_orchestrator import ChatOrchestrator


logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "/message",
    status_code=200,
    summary="Send chat message and get AI response"
)
async def send_message(
    request_data: ChatMessageRequest,
    orchestrator=Depends(get_chat_orchestrator),
    session_data=Depends(get_current_session)
):
    """
    Process chat message and return AI response.
    
    Args:
        request_data: Chat message request data
        request: FastAPI request object
        orchestrator: Chat orchestrator service
        session_data: Validated session data
        accept_language: Preferred language from header
        
    Returns:
        Chat message response with citations and suggestions
        
    Raises:
        RateLimitError: If rate limit exceeded
        ValidationError: If request validation fails
        AppError: If processing fails
    """
    session_id = session_data.get("session_id") or session_data.get("sub")
    
    try:
        # Apply rate limiting
        if settings.rate_limit_enabled:
            try:
                rate_limiter.check_limit(
                    identifier=session_id,
                    limit_type="chat"
                )
                
                # Get remaining requests for headers
                remaining = rate_limiter.get_remaining(
                    identifier=session_id,
                    limit_type="chat"
                )
                
            except RateLimitError as e:
                logger.warning(
                    f"Rate limit exceeded for session {session_id}"
                )
                raise e
        
        # Determine language (request body takes precedence)
        language = request_data.language
        if not language:
            language = "en"
        
        # Generate or use provided conversation_id
        conversation_id = request_data.conversation_id or str(uuid.uuid4())
        
        logger.info(
            f"Processing chat message: session={session_id}, "
            f"conversation={conversation_id}, language={language}, "
            f"message_length={len(request_data.message)}"
        )
        
        # Validate message length
        if len(request_data.message) > settings.max_message_length:
            raise ValidationError(
                message=f"Message exceeds maximum length of {settings.max_message_length} characters",
                field="message",
                details={
                    "max_length": settings.max_message_length,
                    "actual_length": len(request_data.message)
                }
            )
        
        # Process message through orchestrator
        result = await orchestrator.process_message(
            session_id=session_id,
            conversation_id=conversation_id,
            user_message=request_data.message,
            language=language,
            context=request_data.context.model_dump() if request_data.context else None
        )
        
        # Build response
        response = ChatMessageResponse(**result)
        
        logger.info(
            f"Chat message processed successfully: "
            f"message_id={response.message_id}, "
            f"citations={len(response.citations)}, "
            f"suggestions={len(response.suggestions)}, "
            f"processing_time={response.metadata.processing_time}s"
        )
        
        # Add rate limit headers if enabled
        if settings.rate_limit_enabled:
            response_headers = {
                "X-RateLimit-Limit": str(settings.rate_limit_chat_per_minute),
                "X-RateLimit-Remaining": str(remaining or 0),
                "X-RateLimit-Reset": str(60)  # Reset time in seconds
            }
            
            return JSONResponse(
                content=response.model_dump(mode="json", by_alias=True),
                status_code=200,
                headers=response_headers
            )
        
        return JSONResponse(
            content=response.model_dump(mode="json", by_alias=True),
            status_code=200
        )
        
    except RateLimitError as e:
        logger.warning(f"Rate limit error: {e.message}")
        raise e
    
    except ValidationError as e:
        logger.warning(f"Validation error: {e.message}")
        raise e
    
    except AppError as e:
        logger.error(f"Application error: {e.message}", exc_info=True)
        raise e
    
    except Exception as e:
        logger.error(f"Unexpected error processing chat message: {str(e)}", exc_info=True)
        raise AppError(
            message="An unexpected error occurred while processing your message",
            error_code="INTERNAL_ERROR",
            details={"error": str(e)}
        )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=204,
    summary="Clear conversation history",
    description="Delete all messages in a conversation. Cannot be undone."
)
async def clear_conversation(
    conversation_id: str,
    orchestrator: ChatOrchestrator = Depends(get_chat_orchestrator),
    session_data: dict = Depends(get_current_session)
) -> None:
    """
    Clear conversation history.
    
    Args:
        conversation_id: Conversation to clear
        orchestrator: Chat orchestrator service
        session_data: Verified session data
    """
    session_id = session_data.get("session_id") or session_data.get("sub")
    
    logger.info(
        f"Clearing conversation: {conversation_id} for session {session_id}"
    )
    
    try:
        await orchestrator.clear_conversation(conversation_id)
        
        logger.info(f"Conversation cleared: {conversation_id}")
        
    except Exception as e:
        logger.error(
            f"Error clearing conversation {conversation_id}: {str(e)}",
            exc_info=True
        )
        raise AppError(
            message="Failed to clear conversation",
            error_code="CONVERSATION_CLEAR_ERROR",
            details={"conversation_id": conversation_id}
        )
