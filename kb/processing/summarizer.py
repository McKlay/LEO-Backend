"""
Chunk Summarizer - Generate summaries and extract keywords from legal text chunks.

This module provides intelligent summarization using GPT-4 Turbo Preview (GPT-4.1) 
for high-quality legal summaries, especially important for long articles (1000+ words).

GPT-4 Turbo Preview is used instead of GPT-4o-mini because:
- Better comprehension of complex legal text
- Richer, more comprehensive summaries (200-500 tokens)
- Higher quality keyword extraction
- Summaries are used for semantic search embeddings - quality critical
- Note: User has free tokens for gpt-4-turbo-preview
"""

from dataclasses import dataclass
from typing import List, Optional
import json
import hashlib
import re

from adapters.llm.openai_llm import OpenAILLM
from core.logging import get_logger
from core.config import settings

logger = get_logger(__name__)


@dataclass
class ChunkSummary:
    """Summary and keywords for a single chunk.
    
    Summary should be 150-300 words (~200-250 tokens) for comprehensive
    legal context that improves semantic search quality.
    """
    chunk_text: str
    summary: str  # 150-300 words comprehensive summary (not just 2-3 sentences)
    keywords: List[str]  # 5-8 keywords
    confidence: float  # 0.0-1.0


class ChunkSummarizer:
    """
    Generate summaries and extract keywords from legal text chunks.
    Uses GPT-4 Turbo Preview (GPT-4.1) for high-quality legal summaries.
    
    Features:
    - Comprehensive 200-500 token summaries for better semantic search
    - Legal keyword extraction (Article refs, terms, entities)
    - Hash-based caching to avoid re-summarizing identical content
    - Graceful fallback when LLM fails
    
    Cost: ~$0.01-0.02 per chunk (one-time ingestion cost)
    Note: Using gpt-4-turbo-preview as user has free tokens for this model.
    """
    
    def __init__(self, llm: Optional[OpenAILLM] = None, use_llm: bool = True):
        """
        Initialize summarizer.
        
        Args:
            llm: OpenAI LLM adapter (defaults to GPT-4 Turbo Preview if use_llm=True)
            use_llm: Whether to use LLM for summarization (False = always use fallback)
        """
        self.use_llm = use_llm
        if use_llm and llm is None:
            try:
                # Use GPT-4 Turbo Preview (GPT-4.1) for high-quality summaries
                self.llm = OpenAILLM(model="gpt-4.1")
                logger.info("Initialized ChunkSummarizer with GPT-4 Turbo Preview (GPT-4.1)")
            except Exception as e:
                logger.warning(f"Failed to initialize LLM, using fallback mode: {e}")
                self.llm = None
                self.use_llm = False
        else:
            self.llm = llm
            
        self._cache = {}  # Simple hash-based cache
        self.min_words_for_summary = 50
        self.default_temperature = 0.3
        # Increased from 300 to 500 for richer summaries
        self.default_max_tokens = 500
        
    async def summarize(self, chunk_text: str) -> ChunkSummary:
        """
        Generate summary and keywords for a chunk.
        
        Args:
            chunk_text: The text content to summarize
            
        Returns:
            ChunkSummary with summary, keywords, and confidence
        """
        if not chunk_text or not chunk_text.strip():
            logger.warning("Empty chunk text provided")
            return ChunkSummary(
                chunk_text="",
                summary="",
                keywords=[],
                confidence=0.0
            )
        
        # Skip very short chunks - just use truncated text
        word_count = len(chunk_text.split())
        if word_count < self.min_words_for_summary:
            logger.debug(f"Chunk too short ({word_count} words), using truncated text")
            return ChunkSummary(
                chunk_text=chunk_text,
                summary=chunk_text[:150] if len(chunk_text) > 150 else chunk_text,
                keywords=self._extract_basic_keywords(chunk_text),
                confidence=1.0
            )
        
        # Check cache
        cache_key = self._get_cache_key(chunk_text)
        if cache_key in self._cache:
            logger.info("Summary cache hit")
            return self._cache[cache_key]
        
        # Use fallback if LLM is disabled or not available
        if not self.use_llm or self.llm is None:
            logger.debug("Using fallback summarization (LLM disabled)")
            result = self._fallback_summary(chunk_text)
            # Cache fallback results too
            self._cache[cache_key] = result
            return result
        
        # Build prompt for GPT-4o-mini
        prompt = self._build_summary_prompt(chunk_text)
        
        try:
            # Call LLM with JSON mode
            logger.debug(f"Generating summary for chunk ({word_count} words)")
            llm_response = await self.llm.generate(
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=self.default_temperature,
                max_tokens=self.default_max_tokens
            )
            
            # Extract content from LLMResponse
            response = llm_response.content
            
            # Parse response
            result = self._parse_response(response, chunk_text)
            
            # Cache result
            self._cache[cache_key] = result
            
            logger.info(
                f"Summary generated successfully: "
                f"{len(result.summary)} chars, {len(result.keywords)} keywords"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Summarization failed: {e}", exc_info=True)
            # Fallback to basic extraction
            return self._fallback_summary(chunk_text)
    
    async def summarize_batch(
        self, 
        chunks: List[str], 
        max_concurrent: int = 3
    ) -> List[ChunkSummary]:
        """
        Summarize multiple chunks with concurrency control.
        
        Args:
            chunks: List of chunk texts
            max_concurrent: Maximum concurrent LLM calls
            
        Returns:
            List of ChunkSummary objects
        """
        import asyncio
        
        # Process in batches to control concurrency
        results = []
        for i in range(0, len(chunks), max_concurrent):
            batch = chunks[i:i + max_concurrent]
            batch_results = await asyncio.gather(
                *[self.summarize(chunk) for chunk in batch],
                return_exceptions=True
            )
            
            # Handle exceptions
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Batch summarization error for chunk {i+j}: {result}")
                    results.append(self._fallback_summary(batch[j]))
                else:
                    results.append(result)
        
        return results
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key from text hash."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]
    
    def _build_summary_prompt(self, chunk_text: str) -> str:
        """
        Build prompt for GPT-4.1 with target summary length of 150-400 words.
        
        Longer, more comprehensive summaries improve semantic search quality
        by capturing nuanced legal concepts and providing better context for
        vector embeddings. Target: 200-300 words (approximately 150-250 tokens).
        """
        return f"""You are a Philippine labor law expert. Analyze this legal text chunk and provide:

1. A comprehensive 150-400 word summary that captures:
   - Core legal concepts and provisions
   - Who is covered (employers, employees, contractors, etc.)
   - Key rights, obligations, and penalties
   - Relevant procedures or timelines if applicable
   - Any conditions or exceptions
   
2. Highly relevant keywords (5-8 terms) including:
   - Article/Section references (e.g., "Article 97", "Section 3(a)")
   - Legal terms of art (e.g., "overtime pay", "regular wage", "employer obligations")
   - Named entities (e.g., "DOLE", "NLRC", "SSS")
   - Domain concepts (e.g., "minimum wage", "illegal dismissal")

CRITICAL JSON FORMATTING RULES:
- Write summary as ONE CONTINUOUS STRING with NO line breaks inside the string value
- Use only spaces to separate sentences - NEVER use \\n or actual newlines
- Replace any internal double quotes with single quotes or remove them
- Ensure keywords array contains 5-8 string values
- DO NOT wrap response in markdown code blocks (no ```)
- DO NOT include explanatory text before or after the JSON
- VALIDATE that all strings are properly closed with matching quotes
- VALIDATE that all arrays are properly closed with matching brackets

Text to summarize:
{chunk_text[:2000]}

RESPOND WITH ONLY THIS EXACT JSON STRUCTURE (no markdown, no code blocks):
{{
  "summary": "Your 150-400 word summary here as a single continuous string with spaces instead of newlines",
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5", "keyword6", "keyword7", "keyword8"]
}}"""

    def _parse_response(self, response: str, chunk_text: str) -> ChunkSummary:
        """
        Parse LLM JSON response with robust validation and recovery.
        
        Args:
            response: JSON string from LLM
            chunk_text: Original chunk text
            
        Returns:
            ChunkSummary object
        """
        try:
            # First attempt: direct JSON parsing
            data = json.loads(response)
            return self._validate_and_return_summary(data, chunk_text)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response was: {response[:300]}")
            
            # Second attempt: Try to fix common JSON issues
            try:
                fixed_response = self._repair_json(response)
                data = json.loads(fixed_response)
                logger.info("Successfully repaired malformed JSON response")
                return self._validate_and_return_summary(data, chunk_text)
            except Exception as repair_error:
                logger.warning(f"JSON repair failed: {repair_error}")
                return self._fallback_summary(chunk_text)
        except Exception as e:
            logger.error(f"Unexpected error parsing LLM response: {e}")
            return self._fallback_summary(chunk_text)
    
    def _repair_json(self, response: str) -> str:
        """
        Attempt to repair common JSON parsing errors.
        
        Handles:
        - Unterminated strings (missing closing quotes)
        - Incomplete objects/arrays (missing closing braces/brackets)
        - Newlines within string values
        - Embedded code blocks
        
        Args:
            response: Potentially malformed JSON string
            
        Returns:
            Repaired JSON string (best effort)
        """
        # Remove leading/trailing whitespace
        response = response.strip()
        
        # Try to extract JSON from markdown code blocks
        if '```json' in response:
            start = response.find('```json') + 7
            end = response.rfind('```')
            if end > start:
                response = response[start:end].strip()
        elif '```' in response:
            start = response.find('```') + 3
            end = response.rfind('```')
            if end > start:
                response = response[start:end].strip()
        
        # Try to find the JSON object boundaries
        json_start = response.find('{')
        json_end = response.rfind('}')
        
        if json_start != -1 and json_end > json_start:
            # Extract just the JSON part
            response = response[json_start:json_end + 1]
        
        # Replace problematic characters in string values
        # Fix newlines within JSON strings (but preserve structure)
        response = re.sub(r'"\s*\n\s*([^"{}[\],]+)\s*\n\s*"', r'" \1 "', response)
        
        # Count braces to detect incomplete object
        open_braces = response.count('{')
        close_braces = response.count('}')
        open_brackets = response.count('[')
        close_brackets = response.count(']')
        
        # Parse and track quote positions more carefully
        in_escape = False
        quote_positions = []
        i = 0
        while i < len(response):
            char = response[i]
            if char == '\\' and not in_escape:
                in_escape = True
            elif char == '"' and not in_escape:
                quote_positions.append(i)
                in_escape = False
            else:
                in_escape = False
            i += 1
        
        # If odd number of unescaped quotes, we have an unterminated string
        if len(quote_positions) % 2 == 1:
            logger.debug(f"Detected unterminated string at position {quote_positions[-1]}")
            last_quote_pos = quote_positions[-1]
            
            # Find where to close the string - look for structural JSON delimiters
            rest_of_string = response[last_quote_pos + 1:]
            
            # Find the earliest occurrence of a structural delimiter
            delimiters = [',', '}', ']', '\n']
            end_pos = len(rest_of_string)
            
            for delimiter in delimiters:
                pos = rest_of_string.find(delimiter)
                if pos != -1 and pos < end_pos:
                    end_pos = pos
            
            # Insert closing quote before the delimiter
            if end_pos > 0:
                response = (
                    response[:last_quote_pos + 1 + end_pos] + 
                    '"' + 
                    response[last_quote_pos + 1 + end_pos:]
                )
                logger.debug("Added closing quote for unterminated string")
        
        # Add missing closing braces/brackets at the end
        if open_braces > close_braces:
            missing = open_braces - close_braces
            response += '}' * missing
            logger.debug(f"Added {missing} missing closing braces")
        if open_brackets > close_brackets:
            missing = open_brackets - close_brackets
            response += ']' * missing
            logger.debug(f"Added {missing} missing closing brackets")
        
        return response
    
    def _validate_and_return_summary(self, data: dict, chunk_text: str) -> ChunkSummary:
        """
        Validate parsed JSON data and return ChunkSummary.
        
        Args:
            data: Parsed JSON dictionary
            chunk_text: Original chunk text
            
        Returns:
            ChunkSummary object or fallback if validation fails
        """
        try:
            summary = data.get("summary", "").strip() if isinstance(data.get("summary"), str) else ""
            keywords = data.get("keywords", [])
            
            # Validate keywords is a list
            if not isinstance(keywords, list):
                logger.warning(f"Keywords is not a list: {type(keywords)}, using empty list")
                keywords = []
            
            # Ensure keywords are strings and deduplicate (max 8)
            keywords = list(set([str(k).strip() for k in keywords if k and isinstance(k, (str, int))]))[:8]
            
            # If no keywords were extracted, use fallback
            if not keywords:
                logger.warning("No valid keywords extracted from LLM response")
                keywords = self._extract_basic_keywords(chunk_text)
            
            # Validate summary length
            if not summary or len(summary) < 20:
                logger.warning(f"Summary too short ({len(summary)} chars), using fallback")
                return self._fallback_summary(chunk_text)
            
            return ChunkSummary(
                chunk_text=chunk_text,
                summary=summary,
                keywords=keywords,
                confidence=0.9
            )
            
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return self._fallback_summary(chunk_text)
    
    def _fallback_summary(self, chunk_text: str) -> ChunkSummary:
        """
        Fallback when LLM fails - use basic extraction.
        
        Args:
            chunk_text: Original chunk text
            
        Returns:
            ChunkSummary with basic extraction
        """
        # Extract first 150 chars as summary
        summary = chunk_text[:150].strip()
        if len(chunk_text) > 150:
            # Try to end at sentence boundary
            last_period = summary.rfind('.')
            if last_period > 50:
                summary = summary[:last_period + 1]
            else:
                summary += "..."
        
        # Basic keyword extraction
        keywords = self._extract_basic_keywords(chunk_text)
        
        logger.warning(
            f"Using fallback summary: {len(summary)} chars, "
            f"{len(keywords)} keywords"
        )
        
        return ChunkSummary(
            chunk_text=chunk_text,
            summary=summary,
            keywords=keywords,
            confidence=0.5
        )
    
    def _extract_basic_keywords(self, text: str) -> List[str]:
        """
        Extract keywords using regex patterns.
        
        Args:
            text: Text to extract keywords from
            
        Returns:
            List of keywords (max 8)
        """
        keywords = []
        
        # Article references (e.g., "Article 97", "Article 123-A")
        keywords.extend(re.findall(r'Article\s+\d+[-\w]*', text, re.IGNORECASE))
        
        # Section references (e.g., "Section 3", "Section 5(a)")
        keywords.extend(re.findall(r'Section\s+\d+[-\w()]*', text, re.IGNORECASE))
        
        # Named entities (common labor law entities)
        entities = [
            'DOLE', 'NLRC', 'SSS', 'PhilHealth', 'Pag-IBIG', 'POEA',
            'Labor Code', 'Department Order', 'Presidential Decree'
        ]
        for entity in entities:
            if entity.lower() in text.lower():
                keywords.append(entity)
        
        # Common legal terms (if present)
        terms = [
            'overtime pay', 'night shift differential', 'holiday pay',
            'service incentive leave', '13th month pay', 'maternity leave',
            'paternity leave', 'regular wage', 'minimum wage', 'separation pay',
            'just cause', 'authorized cause', 'due process', 'illegal dismissal'
        ]
        for term in terms:
            if term.lower() in text.lower():
                keywords.append(term)
        
        # Deduplicate and limit to 8
        keywords = list(set(keywords))[:8]
        
        return keywords
    
    def clear_cache(self):
        """Clear the summary cache."""
        cache_size = len(self._cache)
        self._cache.clear()
        logger.info(f"Cleared summary cache ({cache_size} entries)")
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        return {
            "size": len(self._cache),
            "keys": list(self._cache.keys())
        }
