"""
Generation pipeline module for LLM response generation.

Handles prompt construction, LLM invocation, and streaming responses.
"""
from typing import List, Dict, Any, Optional, AsyncIterator
import asyncio

from core import get_logger, AppError
from adapters.llm.base import BaseLLM, LLMResponse


logger = get_logger(__name__)


class GenerationPipeline:
    """
    Handles LLM response generation with streaming support.
    
    Orchestrates prompt construction, LLM calls, and response handling.
    """
    
    def __init__(
        self,
        llm: BaseLLM,
        default_temperature: float = 0.3,
        default_max_tokens: int = 1000,
        enable_streaming: bool = True
    ):
        """
        Initialize generation pipeline.
        
        Args:
            llm: LLM adapter instance
            default_temperature: Default temperature for generation (0-1)
            default_max_tokens: Default max tokens for responses
            enable_streaming: Whether to enable streaming by default
        """
        self.llm = llm
        self.default_temperature = default_temperature
        self.default_max_tokens = default_max_tokens
        self.enable_streaming = enable_streaming
        
        logger.info(
            f"Generation pipeline initialized "
            f"(temp={default_temperature}, max_tokens={default_max_tokens}, "
            f"streaming={enable_streaming})"
        )
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a response from the LLM.
        
        Args:
            messages: List of chat messages (role + content)
            temperature: Sampling temperature (uses default if None)
            max_tokens: Maximum tokens to generate (uses default if None)
            **kwargs: Additional LLM parameters
            
        Returns:
            LLM response with content and metadata
            
        Raises:
            AppError: If generation fails
        """
        try:
            # Use defaults if not specified
            temp = temperature if temperature is not None else self.default_temperature
            tokens = max_tokens if max_tokens is not None else self.default_max_tokens
            
            logger.info(
                f"Generating response (temp={temp}, max_tokens={tokens}, "
                f"messages={len(messages)})"
            )
            
            # Call LLM
            response = await self.llm.generate(
                messages=messages,
                temperature=temp,
                max_tokens=tokens,
                **kwargs
            )
            
            logger.info(
                f"Generated response "
                f"(tokens_used={response.tokens_used}, "
                f"finish_reason={response.finish_reason})"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Generation failed: {str(e)}", exc_info=True)
            raise AppError(
                message="Failed to generate response",
                error_code="GENERATION_FAILED",
                status_code=500,
                details={
                    "error": str(e),
                    "message_count": len(messages)
                }
            )
    
    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Generate a streaming response from the LLM.
        
        Args:
            messages: List of chat messages (role + content)
            temperature: Sampling temperature (uses default if None)
            max_tokens: Maximum tokens to generate (uses default if None)
            **kwargs: Additional LLM parameters
            
        Yields:
            Response chunks as they are generated
            
        Raises:
            AppError: If generation fails
        """
        try:
            # Use defaults if not specified
            temp = temperature if temperature is not None else self.default_temperature
            tokens = max_tokens if max_tokens is not None else self.default_max_tokens
            
            logger.info(
                f"Starting streaming generation (temp={temp}, max_tokens={tokens})"
            )
            
            # Stream from LLM
            chunk_count = 0
            async for chunk in self.llm.stream_generate(
                messages=messages,
                temperature=temp,
                max_tokens=tokens,
                **kwargs
            ):
                chunk_count += 1
                yield chunk
            
            logger.info(f"Completed streaming generation ({chunk_count} chunks)")
            
        except Exception as e:
            logger.error(f"Streaming generation failed: {str(e)}", exc_info=True)
            raise AppError(
                message="Failed to stream response",
                error_code="STREAMING_FAILED",
                status_code=500,
                details={
                    "error": str(e),
                    "message_count": len(messages)
                }
            )
    
    async def generate_with_retry(
        self,
        messages: List[Dict[str, str]],
        max_retries: int = 2,
        **kwargs
    ) -> LLMResponse:
        """
        Generate with automatic retry on failures.
        
        Args:
            messages: List of chat messages
            max_retries: Maximum number of retry attempts
            **kwargs: Additional generation parameters
            
        Returns:
            LLM response
            
        Raises:
            AppError: If all retries fail
        """
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                return await self.generate(messages=messages, **kwargs)
                
            except AppError as e:
                last_error = e
                if attempt < max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(
                        f"Generation attempt {attempt + 1} failed, "
                        f"retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"All {max_retries + 1} attempts failed")
        
        # All retries exhausted
        raise last_error
    
    def estimate_token_count(self, text: str) -> int:
        """
        Estimate token count for text (rough approximation).
        
        Args:
            text: Input text
            
        Returns:
            Estimated token count
        """
        # Rough estimate: 1 token ≈ 4 characters for English
        # This is a simplification; use tiktoken for accurate counts
        return len(text) // 4
    
    def validate_message_format(self, messages: List[Dict[str, str]]) -> bool:
        """
        Validate message list format.
        
        Args:
            messages: List of messages to validate
            
        Returns:
            True if valid
            
        Raises:
            AppError: If validation fails
        """
        if not messages:
            raise AppError(
                message="Messages list cannot be empty",
                error_code="INVALID_MESSAGES",
                status_code=400
            )
        
        for idx, msg in enumerate(messages):
            if not isinstance(msg, dict):
                raise AppError(
                    message=f"Message {idx} must be a dictionary",
                    error_code="INVALID_MESSAGE_FORMAT",
                    status_code=400
                )
            
            if "role" not in msg or "content" not in msg:
                raise AppError(
                    message=f"Message {idx} missing 'role' or 'content'",
                    error_code="INVALID_MESSAGE_FIELDS",
                    status_code=400
                )
            
            if msg["role"] not in ["system", "user", "assistant"]:
                raise AppError(
                    message=f"Invalid role '{msg['role']}' in message {idx}",
                    error_code="INVALID_MESSAGE_ROLE",
                    status_code=400
                )
        
        return True
    
    async def generate_clarification(
        self,
        query: str,
        language: str = "en"
    ) -> str:
        """
        Generate a clarification request for vague queries.
        
        Args:
            query: Original vague query
            language: Language code
            
        Returns:
            Clarification message
        """
        clarification_prompts = {
            "en": "I'd be happy to help with your labor law question. Could you please provide more details about your specific situation?",
            "fil": "Masayang tutulungan kita sa iyong tanong tungkol sa labor law. Maaari mo bang ibigay ang mas detalyadong impormasyon tungkol sa iyong sitwasyon?",
            "ceb": "Malipay kong motabang sa imong pangutana bahin sa labor law. Mahimo ba nimo nga mohatag og mas detalyado nga impormasyon bahin sa imong sitwasyon?"
        }
        
        return clarification_prompts.get(language, clarification_prompts["en"])
