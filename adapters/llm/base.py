"""
Base interface for Large Language Model (LLM) adapters.

Defines the contract that all LLM implementations must follow,
enabling easy swapping between different LLM providers.
"""
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional
from pydantic import BaseModel


class Message(BaseModel):
    """Chat message model."""
    
    role: str  # "system", "user", "assistant"
    content: str


class LLMResponse(BaseModel):
    """LLM generation response."""
    
    content: str
    model: str
    tokens_used: int
    finish_reason: Optional[str] = None


class BaseLLM(ABC):
    """
    Base LLM adapter interface.
    
    All LLM implementations (OpenAI, Anthropic, etc.) should
    implement this interface.
    """
    
    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        temperature: float = 0.3,
        max_tokens: int = 2000,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a response from the LLM.
        
        Args:
            messages: Conversation history
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters
            
        Returns:
            LLM response with content and metadata
            
        Raises:
            LLMError: If generation fails
        """
        pass
    
    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        temperature: float = 0.3,
        max_tokens: int = 2000,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Stream a response from the LLM.
        
        Args:
            messages: Conversation history
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters
            
        Yields:
            Response chunks as they are generated
            
        Raises:
            LLMError: If streaming fails
        """
        pass
    
    @abstractmethod
    async def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        pass
