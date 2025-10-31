"""
LangChain memory adapter for conversation history management.

Uses LangChain's ConversationBufferMemory for in-memory storage
with optional Redis persistence.
"""
from typing import Optional, List
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from core import get_logger, AppError
from adapters.memory.base import BaseMemory, ConversationHistory, ConversationMessage

logger = get_logger(__name__)


class LangChainMemory(BaseMemory):
    """
    LangChain-based conversation memory implementation.
    
    Stores conversation history in memory with option to persist to Redis.
    """
    
    def __init__(self, max_token_limit: int = 4000):
        """
        Initialize LangChain memory adapter.
        
        Args:
            max_token_limit: Maximum tokens to keep in memory
        """
        self.max_token_limit = max_token_limit
        self._memories: dict[str, ChatMessageHistory] = {}
        
        logger.info(f"LangChain memory initialized with token limit: {max_token_limit}")
    
    def _get_or_create_memory(self, session_id: str) -> ChatMessageHistory:
        """
        Get or create memory for a session.
        
        Args:
            session_id: Session/conversation identifier
            
        Returns:
            ChatMessageHistory instance
        """
        if session_id not in self._memories:
            self._memories[session_id] = ChatMessageHistory()
            logger.debug(f"Created new memory for session: {session_id}")
        
        return self._memories[session_id]
    
    async def get_history(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> ConversationHistory:
        """
        Retrieve conversation history for a session.
        
        Args:
            session_id: Session/conversation identifier
            limit: Maximum number of messages to retrieve
            
        Returns:
            Conversation history
        """
        try:
            memory = self._get_or_create_memory(session_id)
            
            # Get messages from memory
            messages: List[BaseMessage] = memory.messages
            
            # Apply limit if specified
            if limit and len(messages) > limit:
                messages = messages[-limit:]
            
            # Convert to our format
            conversation_messages = []
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    role = "user"
                elif isinstance(msg, AIMessage):
                    role = "assistant"
                else:
                    role = "system"
                
                conversation_messages.append(
                    ConversationMessage(
                        role=role,
                        content=msg.content
                    )
                )
            
            return ConversationHistory(
                session_id=session_id,
                messages=conversation_messages
            )
            
        except Exception as e:
            logger.error(f"Error retrieving history: {str(e)}", exc_info=True)
            raise AppError(
                message="Failed to retrieve conversation history",
                error_code="MEMORY_RETRIEVAL_FAILED",
                status_code=500,
                details={"error": str(e)}
            )
    
    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str
    ) -> None:
        """
        Add a message to conversation history.
        
        Args:
            session_id: Session/conversation identifier
            role: Message role ("user", "assistant", "system")
            content: Message content
        """
        try:
            memory = self._get_or_create_memory(session_id)
            
            # Add message based on role
            if role == "user":
                memory.add_user_message(content)
            elif role == "assistant":
                memory.add_ai_message(content)
            else:
                # For system messages, add as user message with prefix
                memory.add_user_message(f"[System] {content}")
            
            logger.debug(f"Added {role} message to session {session_id}")
            
        except Exception as e:
            logger.error(f"Error adding message: {str(e)}", exc_info=True)
            raise AppError(
                message="Failed to add message to conversation history",
                error_code="MEMORY_ADD_FAILED",
                status_code=500,
                details={"error": str(e)}
            )
    
    async def clear_history(self, session_id: str) -> None:
        """
        Clear conversation history for a session.
        
        Args:
            session_id: Session/conversation identifier
        """
        try:
            if session_id in self._memories:
                self._memories[session_id].clear()
                logger.info(f"Cleared history for session: {session_id}")
            else:
                logger.warning(f"Attempted to clear non-existent session: {session_id}")
                
        except Exception as e:
            logger.error(f"Error clearing history: {str(e)}", exc_info=True)
            raise AppError(
                message="Failed to clear conversation history",
                error_code="MEMORY_CLEAR_FAILED",
                status_code=500,
                details={"error": str(e)}
            )
    
    async def delete_session(self, session_id: str) -> None:
        """
        Delete a session and its history.
        
        Args:
            session_id: Session/conversation identifier
        """
        try:
            if session_id in self._memories:
                del self._memories[session_id]
                logger.info(f"Deleted session: {session_id}")
            else:
                logger.warning(f"Attempted to delete non-existent session: {session_id}")
                
        except Exception as e:
            logger.error(f"Error deleting session: {str(e)}", exc_info=True)
            raise AppError(
                message="Failed to delete session",
                error_code="MEMORY_DELETE_FAILED",
                status_code=500,
                details={"error": str(e)}
            )
    
    def get_message_count(self, session_id: str) -> int:
        """
        Get the number of messages in a session.
        
        Args:
            session_id: Session/conversation identifier
            
        Returns:
            Number of messages
        """
        if session_id not in self._memories:
            return 0
        
        return len(self._memories[session_id].messages)
    
    def session_exists(self, session_id: str) -> bool:
        """
        Check if a session exists.
        
        Args:
            session_id: Session/conversation identifier
            
        Returns:
            True if session exists
        """
        return session_id in self._memories
