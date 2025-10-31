"""
OpenAI embeddings adapter implementation.

Uses OpenAI's text-embedding-3-small model for generating embeddings.
"""
from typing import Optional
from openai import AsyncOpenAI

from core import get_logger, AppError
from core.config import Settings
from adapters.embeddings.base import (
    BaseEmbeddings,
    EmbeddingResponse,
    BatchEmbeddingResponse
)

logger = get_logger(__name__)


class OpenAIEmbeddings(BaseEmbeddings):
    """
    OpenAI embeddings implementation.
    
    Uses text-embedding-3-small model (1536 dimensions) for
    generating text embeddings.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        settings: Optional[Settings] = None
    ):
        """
        Initialize OpenAI embeddings adapter.
        
        Args:
            api_key: OpenAI API key (or provide settings)
            model: Model name (or provide settings)
            settings: Application settings (alternative to individual params)
        """
        if settings:
            self.api_key = settings.openai_api_key
            self.model = settings.openai_embedding_model
            self.dimension = settings.embedding_dimension
        else:
            self.api_key = api_key
            self.model = model or "text-embedding-3-small"
            self.dimension = 1536
        
        self.client = AsyncOpenAI(api_key=self.api_key)
        
        logger.info(f"OpenAI embeddings initialized with model: {self.model}")
    
    async def embed_text(self, text: str) -> EmbeddingResponse:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding response with vector and metadata
            
        Raises:
            AppError: If embedding generation fails
        """
        try:
            # Clean and validate text
            text = text.strip()
            if not text:
                raise AppError(
                    message="Cannot embed empty text",
                    error_code="INVALID_INPUT",
                    status_code=400
                )
            
            # Generate embedding
            response = await self.client.embeddings.create(
                input=text,
                model=self.model
            )
            
            embedding_data = response.data[0]
            
            return EmbeddingResponse(
                embedding=embedding_data.embedding,
                model=response.model,
                tokens_used=response.usage.total_tokens
            )
            
        except AppError:
            raise
        except Exception as e:
            logger.error(f"OpenAI embedding error: {str(e)}", exc_info=True)
            raise AppError(
                message="Failed to generate embedding",
                error_code="EMBEDDING_GENERATION_FAILED",
                status_code=500,
                details={"error": str(e)}
            )
    
    async def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 100
    ) -> BatchEmbeddingResponse:
        """
        Generate embeddings for multiple texts in batches.
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts per batch (max 2048 for OpenAI)
            
        Returns:
            Batch embedding response with vectors and metadata
            
        Raises:
            AppError: If batch embedding generation fails
        """
        try:
            if not texts:
                raise AppError(
                    message="Cannot embed empty text list",
                    error_code="INVALID_INPUT",
                    status_code=400
                )
            
            # Clean texts
            texts = [t.strip() for t in texts if t.strip()]
            
            if not texts:
                raise AppError(
                    message="All texts are empty after cleaning",
                    error_code="INVALID_INPUT",
                    status_code=400
                )
            
            # Limit batch size to OpenAI's maximum
            if batch_size > 2048:
                batch_size = 2048
                logger.warning(f"Batch size limited to OpenAI maximum: 2048")
            
            all_embeddings = []
            total_tokens = 0
            model_name = None
            
            # Process in batches
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                
                response = await self.client.embeddings.create(
                    input=batch,
                    model=self.model
                )
                
                # Extract embeddings in order
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
                total_tokens += response.usage.total_tokens
                model_name = response.model
                
                logger.debug(
                    f"Processed batch {i//batch_size + 1}: "
                    f"{len(batch)} texts, {response.usage.total_tokens} tokens"
                )
            
            return BatchEmbeddingResponse(
                embeddings=all_embeddings,
                model=model_name or self.model,
                total_tokens_used=total_tokens
            )
            
        except AppError:
            raise
        except Exception as e:
            logger.error(f"OpenAI batch embedding error: {str(e)}", exc_info=True)
            raise AppError(
                message="Failed to generate batch embeddings",
                error_code="BATCH_EMBEDDING_FAILED",
                status_code=500,
                details={"error": str(e)}
            )
    
    def get_dimension(self) -> int:
        """
        Get the embedding dimension for the current model.
        
        Returns:
            Embedding dimension
        """
        # Map of OpenAI models to dimensions
        model_dimensions = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        
        return model_dimensions.get(self.model, 1536)
