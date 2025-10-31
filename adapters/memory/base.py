"""
Base interface for conversation memory adapters.

Defines the contract for conversation memory/history management,
enabling different storage backends (in-memory, Redis, database).
"""
from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel


class ConversationMessage(BaseModel):
    """Conversation message model."""
    
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[str] = None


class BaseMemory(ABC):
    """
    Base memory adapter interface.
    
    All memory implementations (in-memory, Redis, LangChain, etc.)
    should implement this interface.
    """
    
    @abstractmethod
    async def get_history(
        self,
        conversation_id: str,
        limit: Optional[int] = None
    ) -> list[ConversationMessage]:
        """
        Get conversation history.
        
        Args:
            conversation_id: Conversation identifier
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of conversation messages
        """
        pass
    
    @abstractmethod
    async def append_message(
        self,
        conversation_id: str,
        message: ConversationMessage
    ) -> None:
        """
        Append message to conversation history.
        
        Args:
            conversation_id: Conversation identifier
            message: Message to append
        """
        pass
    
    @abstractmethod
    async def clear_history(self, conversation_id: str) -> None:
        """
        Clear conversation history.
        
        Args:
            conversation_id: Conversation identifier
        """
        pass
    
    @abstractmethod
    async def delete_conversation(self, conversation_id: str) -> None:
        """
        Delete entire conversation.
        
        Args:
            conversation_id: Conversation identifier
        """
        pass
