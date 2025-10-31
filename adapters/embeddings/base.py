"""
Base interface for embedding model adapters.

Defines the contract for text embedding generation,
enabling easy swapping between embedding providers.
"""
from abc import ABC, abstractmethod
from pydantic import BaseModel


class EmbeddingResponse(BaseModel):
    """Embedding generation response."""
    
    embedding: list[float]
    model: str
    tokens_used: int


class BatchEmbeddingResponse(BaseModel):
    """Batch embedding generation response."""
    
    embeddings: list[list[float]]
    model: str
    total_tokens_used: int


class BaseEmbeddings(ABC):
    """
    Base embeddings adapter interface.
    
    All embedding implementations (OpenAI, Cohere, etc.) should
    implement this interface.
    """
    
    @abstractmethod
    async def embed_text(self, text: str) -> EmbeddingResponse:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding response with vector and metadata
            
        Raises:
            ExternalServiceError: If embedding generation fails
        """
        pass
    
    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> BatchEmbeddingResponse:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            Batch embedding response
            
        Raises:
            ExternalServiceError: If batch embedding fails
        """
        pass
    
    @abstractmethod
    def get_dimension(self) -> int:
        """
        Get embedding dimension.
        
        Returns:
            Embedding vector dimension
        """
        pass
