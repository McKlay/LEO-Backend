"""
OpenAI LLM adapter implementation.

Uses OpenAI's GPT models for chat completion with streaming support.
"""
from typing import AsyncGenerator, Optional
from openai import AsyncOpenAI
import json

from core import get_logger, AppError
from core.config import Settings
from adapters.llm.base import BaseLLM, Message, LLMResponse

logger = get_logger(__name__)


class OpenAILLM(BaseLLM):
    """
    OpenAI LLM implementation with streaming support.
    
    Uses GPT-4.1 model for chat completion.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        settings: Optional[Settings] = None
    ):
        """
        Initialize OpenAI LLM adapter.
        
        Args:
            api_key: OpenAI API key (or provide settings)
            model: Model name (or provide settings)
            settings: Application settings (alternative to individual params)
        """
        if settings:
            self.api_key = settings.openai_api_key
            self.model = settings.openai_llm_model
            self.default_temperature = settings.llm_temperature
            self.default_max_tokens = settings.llm_max_tokens
        else:
            self.api_key = api_key
            self.model = model or "gpt-4.1"
            self.default_temperature = 0.3
            self.default_max_tokens = 1000
        
        self.client = AsyncOpenAI(api_key=self.api_key)
        
        logger.info(f"OpenAI LLM initialized with model: {self.model}")
    
    async def generate(
        self,
        messages: list[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a response from the LLM.
        
        Args:
            messages: Conversation history
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional model-specific parameters
            
        Returns:
            LLM response with content and metadata
            
        Raises:
            AppError: If generation fails
        """
        try:
            # Use defaults if not specified
            temperature = temperature if temperature is not None else self.default_temperature
            max_tokens = max_tokens if max_tokens is not None else self.default_max_tokens
            
            # Convert Message objects to OpenAI format
            # Handle both dict and Message objects
            openai_messages = []
            for msg in messages:
                if isinstance(msg, dict):
                    openai_messages.append({"role": msg["role"], "content": msg["content"]})
                else:
                    openai_messages.append({"role": msg.role, "content": msg.content})
            
            # Log the request
            logger.info(
                f"Generating response: {len(messages)} messages, "
                f"temp={temperature}, max_tokens={max_tokens}"
            )
            
            # Make API call
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            # Extract response
            choice = response.choices[0]
            
            return LLMResponse(
                content=choice.message.content or "",
                model=response.model,
                tokens_used=response.usage.total_tokens,
                finish_reason=choice.finish_reason
            )
            
        except Exception as e:
            logger.error(f"OpenAI LLM generation error: {str(e)}", exc_info=True)
            raise AppError(
                message="Failed to generate LLM response",
                error_code="LLM_GENERATION_FAILED",
                status_code=500,
                details={"error": str(e)}
            )
    
    async def stream_generate(
        self,
        messages: list[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Stream response generation with improved settings for conversational tone.
        
        Optimized for GPT-4 Turbo with rich-context grounding:
        - Higher max_tokens for comprehensive responses (1500 vs 1000)
        - Balanced temperature for natural yet precise tone (0.7 vs 0.3)
        
        Args:
            messages: Conversation history
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional model-specific parameters
            
        Yields:
            Text chunks as they are generated
            
        Raises:
            AppError: If streaming fails
        """
        try:
            # Use optimized defaults for conversational responses
            temperature = temperature if temperature is not None else 0.7  # More natural
            max_tokens = max_tokens if max_tokens is not None else 1500  # Comprehensive
            
            # Convert Message objects to OpenAI format
            openai_messages = []
            for msg in messages:
                if isinstance(msg, dict):
                    openai_messages.append({"role": msg["role"], "content": msg["content"]})
                else:
                    openai_messages.append({"role": msg.role, "content": msg.content})
            
            logger.info(
                f"Streaming response: {len(messages)} messages, "
                f"temp={temperature}, max_tokens={max_tokens}"
            )
            
            # Make streaming API call
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs
            )
            
            # Stream response chunks
            async for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield delta.content
            
        except Exception as e:
            logger.error(f"OpenAI LLM streaming error: {str(e)}", exc_info=True)
            raise AppError(
                message="Failed to stream LLM response",
                error_code="LLM_STREAMING_FAILED",
                status_code=500,
                details={"error": str(e)}
            )
    
    async def generate_with_functions(
        self,
        messages: list[Message],
        functions: list[dict],
        function_call: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a response with function calling support.
        
        Useful for structured output and tool use.
        
        Args:
            messages: Conversation history
            functions: Function definitions for the model
            function_call: Force specific function call ("auto", "none", or function name)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional model-specific parameters
            
        Returns:
            LLM response with content and metadata
            
        Raises:
            AppError: If generation fails
        """
        try:
            temperature = temperature if temperature is not None else self.default_temperature
            max_tokens = max_tokens if max_tokens is not None else self.default_max_tokens
            
            openai_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ]
            
            # Prepare parameters
            params = {
                "model": self.model,
                "messages": openai_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "functions": functions,
                **kwargs
            }
            
            if function_call:
                params["function_call"] = function_call
            
            response = await self.client.chat.completions.create(**params)
            
            choice = response.choices[0]
            
            # Check if function was called
            if choice.message.function_call:
                content = json.dumps({
                    "function_call": {
                        "name": choice.message.function_call.name,
                        "arguments": choice.message.function_call.arguments
                    }
                })
            else:
                content = choice.message.content or ""
            
            return LLMResponse(
                content=content,
                model=response.model,
                tokens_used=response.usage.total_tokens,
                finish_reason=choice.finish_reason
            )
            
        except Exception as e:
            logger.error(f"OpenAI function calling error: {str(e)}", exc_info=True)
            raise AppError(
                message="Failed to generate LLM response with functions",
                error_code="LLM_FUNCTION_CALL_FAILED",
                status_code=500,
                details={"error": str(e)}
            )
    
    async def analyze_query(
        self,
        messages: list[Message],
        temperature: float = 0.1,
        max_tokens: int = 700,
        **kwargs
    ) -> LLMResponse:
        """
        Analyze query using GPT-4o-mini for fast, structured analysis.
        
        Optimized specifically for query analysis:
        - Uses GPT-4o-mini model (faster, cheaper than GPT-4 Turbo)
        - Very low temperature (0.1) for deterministic JSON output
        - Lower max_tokens (500) for compact structured responses
        - Separate from main response generation pipeline
        
        Args:
            messages: Analysis prompt (system + user query)
            temperature: Very low for structured output (default: 0.1)
            max_tokens: Tokens for JSON response (default: 500)
            **kwargs: Additional OpenAI-specific parameters
            
        Returns:
            LLM response with JSON analysis
            
        Raises:
            AppError: If analysis fails
        """
        try:
            # Convert Message objects to OpenAI format
            openai_messages = []
            for msg in messages:
                if isinstance(msg, dict):
                    openai_messages.append({"role": msg["role"], "content": msg["content"]})
                else:
                    openai_messages.append({"role": msg.role, "content": msg.content})
            
            logger.info(
                f"Query analysis with GPT-4o-mini: "
                f"{len(messages)} messages, temp={temperature}, max_tokens={max_tokens}"
            )
            
            # Use GPT-4o-mini for fast, cost-effective structured analysis
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",  # Fast model for analysis
                messages=openai_messages,
                temperature=temperature,  # Very low for deterministic output
                max_tokens=max_tokens,  # Compact JSON response
                response_format={"type": "json_object"},  # Force JSON output
                **kwargs
            )
            
            choice = response.choices[0]
            
            logger.info(
                f"Query analysis complete: "
                f"tokens={response.usage.total_tokens}, "
                f"model={response.model}"
            )
            
            return LLMResponse(
                content=choice.message.content or "{}",
                model=response.model,
                tokens_used=response.usage.total_tokens,
                finish_reason=choice.finish_reason
            )
            
        except Exception as e:
            logger.error(f"Query analysis error: {str(e)}", exc_info=True)
            raise AppError(
                message="Failed to analyze query",
                error_code="QUERY_ANALYSIS_FAILED",
                status_code=500,
                details={"error": str(e)}
            )
    
    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text (rough approximation).
        
        Args:
            text: Input text
            
        Returns:
            Estimated token count
        """
        # Rough estimate: 1 token ≈ 4 characters for English
        # For production, use tiktoken library for accurate counts
        return len(text) // 4
