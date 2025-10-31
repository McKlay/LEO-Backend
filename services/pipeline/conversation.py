"""
Conversation pipeline module for multi-turn chat management.

Handles conversation state, memory management, and context windows.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime

from core import get_logger, AppError
from adapters.memory.base import BaseMemory, ConversationHistory


logger = get_logger(__name__)


class ConversationPipeline:
    """
    Manages multi-turn conversations with memory.
    
    Handles conversation history, context windows, and session state.
    """
    
    def __init__(
        self,
        memory: BaseMemory,
        max_history_messages: int = 10,
        context_window_tokens: int = 4000
    ):
        """
        Initialize conversation pipeline.
        
        Args:
            memory: Memory adapter for conversation storage
            max_history_messages: Maximum messages to keep in history
            context_window_tokens: Maximum tokens for context window
        """
        self.memory = memory
        self.max_history_messages = max_history_messages
        self.context_window_tokens = context_window_tokens
        
        logger.info(
            f"Conversation pipeline initialized "
            f"(max_messages={max_history_messages}, "
            f"context_tokens={context_window_tokens})"
        )
    
    async def get_conversation_context(
        self,
        session_id: str,
        include_last_n: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Get conversation context for a session.
        
        Args:
            session_id: Session identifier
            include_last_n: Number of recent messages to include
            
        Returns:
            List of message dictionaries (role + content)
        """
        try:
            # Get history from memory
            history = await self.memory.get_history(
                session_id=session_id,
                limit=include_last_n or self.max_history_messages
            )
            
            # Convert to message format
            messages = [
                {"role": msg.role, "content": msg.content}
                for msg in history.messages
            ]
            
            logger.debug(
                f"Retrieved {len(messages)} messages for session {session_id}"
            )
            
            return messages
            
        except Exception as e:
            logger.error(f"Failed to get conversation context: {str(e)}", exc_info=True)
            # Return empty context on error rather than failing
            return []
    
    async def add_user_message(
        self,
        session_id: str,
        content: str
    ) -> None:
        """
        Add a user message to conversation history.
        
        Args:
            session_id: Session identifier
            content: Message content
        """
        try:
            await self.memory.add_message(
                session_id=session_id,
                role="user",
                content=content
            )
            
            logger.debug(f"Added user message to session {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to add user message: {str(e)}", exc_info=True)
            raise AppError(
                message="Failed to save user message",
                error_code="CONVERSATION_ADD_FAILED",
                status_code=500,
                details={"error": str(e)}
            )
    
    async def add_assistant_message(
        self,
        session_id: str,
        content: str
    ) -> None:
        """
        Add an assistant message to conversation history.
        
        Args:
            session_id: Session identifier
            content: Message content
        """
        try:
            await self.memory.add_message(
                session_id=session_id,
                role="assistant",
                content=content
            )
            
            logger.debug(f"Added assistant message to session {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to add assistant message: {str(e)}", exc_info=True)
            raise AppError(
                message="Failed to save assistant message",
                error_code="CONVERSATION_ADD_FAILED",
                status_code=500,
                details={"error": str(e)}
            )
    
    async def clear_conversation(self, session_id: str) -> None:
        """
        Clear conversation history for a session.
        
        Args:
            session_id: Session identifier
        """
        try:
            await self.memory.clear_history(session_id)
            logger.info(f"Cleared conversation for session {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to clear conversation: {str(e)}", exc_info=True)
            raise AppError(
                message="Failed to clear conversation",
                error_code="CONVERSATION_CLEAR_FAILED",
                status_code=500,
                details={"error": str(e)}
            )
    
    async def get_conversation_summary(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Get summary information about a conversation.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Summary dictionary with message counts, etc.
        """
        try:
            history = await self.memory.get_history(session_id)
            
            # Count messages by role
            user_count = sum(1 for m in history.messages if m.role == "user")
            assistant_count = sum(1 for m in history.messages if m.role == "assistant")
            
            summary = {
                "session_id": session_id,
                "total_messages": len(history.messages),
                "user_messages": user_count,
                "assistant_messages": assistant_count,
                "has_history": len(history.messages) > 0
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get conversation summary: {str(e)}", exc_info=True)
            return {
                "session_id": session_id,
                "total_messages": 0,
                "user_messages": 0,
                "assistant_messages": 0,
                "has_history": False,
                "error": str(e)
            }
    
    def is_clarification_needed(
        self,
        query: str,
        min_query_length: int = 10
    ) -> bool:
        """
        Determine if a query is too vague and needs clarification.
        
        Args:
            query: User query
            min_query_length: Minimum acceptable query length
            
        Returns:
            True if clarification is needed
        """
        # Simple heuristics for vague queries
        query_stripped = query.strip()
        
        # Too short
        if len(query_stripped) < min_query_length:
            return True
        
        # Single word queries
        if len(query_stripped.split()) <= 2:
            return True
        
        # Check for vague patterns
        vague_patterns = [
            "help",
            "hi",
            "hello",
            "kumusta",
            "what",
            "how",
            "why"
        ]
        
        query_lower = query_stripped.lower()
        if any(query_lower == pattern for pattern in vague_patterns):
            return True
        
        return False
    
    def estimate_token_count(self, messages: List[Dict[str, str]]) -> int:
        """
        Estimate total token count for message list.
        
        Args:
            messages: List of messages
            
        Returns:
            Estimated token count
        """
        total_chars = sum(len(m.get("content", "")) for m in messages)
        # Rough estimate: 1 token ≈ 4 characters
        return total_chars // 4
    
    def prune_history_by_tokens(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Prune message history to fit within token limit.
        
        Args:
            messages: List of messages
            max_tokens: Maximum tokens (uses default if None)
            
        Returns:
            Pruned message list
        """
        max_tok = max_tokens or self.context_window_tokens
        
        # Always keep system message if present
        system_messages = [m for m in messages if m.get("role") == "system"]
        other_messages = [m for m in messages if m.get("role") != "system"]
        
        # Estimate tokens and prune from oldest
        pruned = other_messages.copy()
        while self.estimate_token_count(system_messages + pruned) > max_tok:
            if len(pruned) <= 2:  # Keep at least last 2 messages
                break
            pruned.pop(0)  # Remove oldest
        
        result = system_messages + pruned
        
        if len(result) < len(messages):
            logger.debug(
                f"Pruned history from {len(messages)} to {len(result)} messages"
            )
        
        return result
