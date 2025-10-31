"""
Base interface for content moderation adapters.

Defines the contract for content moderation services,
enabling easy swapping between providers (OpenAI, Azure, etc.).
"""
from abc import ABC, abstractmethod
from pydantic import BaseModel


class ModerationCategory(BaseModel):
    """Moderation category with score."""
    
    category: str
    flagged: bool
    score: float


class ModerationResult(BaseModel):
    """Content moderation result."""
    
    flagged: bool
    categories: list[ModerationCategory]
    overall_score: float = 0.0


class BaseModeration(ABC):
    """
    Base moderation adapter interface.
    
    All moderation implementations (OpenAI, Perspective API, etc.)
    should implement this interface.
    """
    
    @abstractmethod
    async def check(self, text: str) -> ModerationResult:
        """
        Check text for policy violations.
        
        Args:
            text: Text to moderate
            
        Returns:
            Moderation result with flagged categories
            
        Raises:
            ExternalServiceError: If moderation check fails
        """
        pass
    
    @abstractmethod
    def is_safe(self, result: ModerationResult) -> bool:
        """
        Determine if content is safe based on moderation result.
        
        Args:
            result: Moderation result
            
        Returns:
            True if content is safe, False otherwise
        """
        pass
