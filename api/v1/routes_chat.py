"""
Chat API routes.

Implements streaming chat message endpoint for processing chat messages with SSE.
"""
import uuid
import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from core import get_logger, AppError, settings
from core.exceptions import RateLimitError, ValidationError
from core.rate_limit import rate_limiter
from api.v1.schemas_chat import ChatMessageRequest
from app.containers import get_chat_orchestrator
from app.middleware.auth import get_current_session
from services.chat_orchestrator import ChatOrchestrator


logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "/message/stream",
    status_code=200,
    summary="Send chat message and get streaming AI response"
)
async def send_message_stream(
    request_data: ChatMessageRequest,
    orchestrator=Depends(get_chat_orchestrator),
    session_data=Depends(get_current_session)
):
    """
    Process chat message and return streaming AI response via Server-Sent Events (SSE).
    
    This endpoint streams the response as it's generated, providing better perceived
    performance and allowing real-time display of the AI's response.
    
    **Event Types**:
    - `metadata`: Initial processing metadata (retrieval time, citations count)
    - `content_chunk`: Chunks of the response text as they're generated
    - `citations`: Complete citation data
    - `complete`: Final message with all data
    - `error`: Error information if processing fails
    
    Args:
        request_data: Chat message request data
        orchestrator: Chat orchestrator service
        session_data: Validated session data
        
    Returns:
        Server-Sent Events stream with response chunks
        
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
            except RateLimitError as e:
                logger.warning(f"Rate limit exceeded for session {session_id}")
                raise e
        
        # Determine language
        language = request_data.language or "en"
        
        # Generate or use provided conversation_id
        conversation_id = request_data.conversation_id or str(uuid.uuid4())
        
        logger.info(
            f"Processing streaming chat message: session={session_id}, "
            f"conversation={conversation_id}, language={language}"
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
        
        # Create async generator for SSE streaming
        async def event_generator():
            """Generate Server-Sent Events from orchestrator stream."""
            try:
                async for event in orchestrator.process_message_stream(
                    session_id=session_id,
                    conversation_id=conversation_id,
                    user_message=request_data.message,
                    language=language,
                    context=request_data.context.model_dump() if request_data.context else None
                ):
                    # Format as SSE event
                    event_type = event.get("type", "message")
                    event_data = event.get("data", {})
                    
                    # Send event as "data: {json}\n\n"
                    sse_message = f"event: {event_type}\ndata: {json.dumps(event_data)}\n\n"
                    yield sse_message
                    
            except Exception as e:
                logger.error(f"Streaming error: {str(e)}", exc_info=True)
                error_event = {
                    "error": str(e),
                    "error_code": "STREAMING_ERROR"
                }
                yield f"event: error\ndata: {json.dumps(error_event)}\n\n"
        
        # Return SSE streaming response
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
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
        logger.error(f"Unexpected error in streaming: {str(e)}", exc_info=True)
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
