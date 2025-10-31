"""
Base interface for conversation memory adapters.

Defines the contract for conversation memory/history management,
enabling different storage backends (in-memory, Redis, database).
"""
from abc import ABC, abstractmethod
from typing import Optional, List
from pydantic import BaseModel


class ConversationMessage(BaseModel):
    """Conversation message model."""
    
    role: str  # "user", "assistant", or "system"
    content: str
    timestamp: Optional[str] = None


class ConversationHistory(BaseModel):
    """Conversation history container."""
    
    session_id: str
    messages: List[ConversationMessage]


class BaseMemory(ABC):
    """
    Base memory adapter interface.
    
    All memory implementations (in-memory, Redis, LangChain, etc.)
    should implement this interface.
    """
    
    @abstractmethod
    async def get_history(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> ConversationHistory:
        """
        Get conversation history.
        
        Args:
            session_id: Session/conversation identifier
            limit: Maximum number of messages to retrieve
            
        Returns:
            Conversation history
        """
        pass
    
    @abstractmethod
    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str
    ) -> None:
        """
        Add message to conversation history.
        
        Args:
            session_id: Session/conversation identifier
            role: Message role ("user", "assistant", "system")
            content: Message content
        """
        pass
    
    @abstractmethod
    async def clear_history(self, session_id: str) -> None:
        """
        Clear conversation history.
        
        Args:
            session_id: Session/conversation identifier
        """
        pass
    
    @abstractmethod
    async def delete_session(self, session_id: str) -> None:
        """
        Delete entire conversation session.
        
        Args:
            session_id: Session/conversation identifier
        """
        pass
