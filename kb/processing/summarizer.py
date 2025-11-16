"""
Chunk Summarizer - Generate summaries and extract keywords from legal text chunks.

This module provides intelligent summarization using GPT-4o-mini for cost efficiency
while maintaining high-quality legal keyword extraction.
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
    """Summary and keywords for a single chunk."""
    chunk_text: str
    summary: str  # 2-3 sentences
    keywords: List[str]  # 5-8 keywords
    confidence: float  # 0.0-1.0


class ChunkSummarizer:
    """
    Generate summaries and extract keywords from legal text chunks.
    Uses GPT-4o-mini for cost efficiency.
    
    Features:
    - Concise 2-3 sentence summaries for chunks >50 words
    - Legal keyword extraction (Article refs, terms, entities)
    - Hash-based caching to avoid re-summarizing identical content
    - Graceful fallback when LLM fails
    """
    
    def __init__(self, llm: Optional[OpenAILLM] = None, use_llm: bool = True):
        """
        Initialize summarizer.
        
        Args:
            llm: OpenAI LLM adapter (defaults to GPT-4o-mini if use_llm=True)
            use_llm: Whether to use LLM for summarization (False = always use fallback)
        """
        self.use_llm = use_llm
        if use_llm and llm is None:
            try:
                self.llm = OpenAILLM(model="gpt-4o-mini")
            except Exception as e:
                logger.warning(f"Failed to initialize LLM, using fallback mode: {e}")
                self.llm = None
                self.use_llm = False
        else:
            self.llm = llm
            
        self._cache = {}  # Simple hash-based cache
        self.min_words_for_summary = 50
        self.default_temperature = 0.3
        self.default_max_tokens = 300
        
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
        """Build prompt for GPT-4o-mini."""
        return f"""Analyze this Philippine labor law text chunk and provide:

1. A concise 2-3 sentence summary that captures the key legal concepts
2. 5-8 relevant keywords including:
   - Article/Section references (e.g., "Article 97", "Section 3(a)")
   - Legal terms (e.g., "overtime pay", "regular wage", "employer obligations")
   - Named entities (e.g., "DOLE", "NLRC", "SSS")

Text:
{chunk_text[:2000]}

Respond ONLY in valid JSON format:
{{
  "summary": "2-3 sentence summary here",
  "keywords": ["keyword1", "keyword2", "keyword3", ...]
}}"""

    def _parse_response(self, response: str, chunk_text: str) -> ChunkSummary:
        """
        Parse LLM JSON response.
        
        Args:
            response: JSON string from LLM
            chunk_text: Original chunk text
            
        Returns:
            ChunkSummary object
        """
        try:
            data = json.loads(response)
            summary = data.get("summary", "").strip()
            keywords = data.get("keywords", [])
            
            # Validate keywords is a list
            if not isinstance(keywords, list):
                logger.warning(f"Keywords is not a list: {type(keywords)}")
                keywords = []
            
            # Ensure keywords are strings and deduplicate
            keywords = list(set([str(k).strip() for k in keywords if k]))[:8]
            
            # Validate summary
            if not summary:
                logger.warning("Empty summary from LLM, using fallback")
                return self._fallback_summary(chunk_text)
            
            return ChunkSummary(
                chunk_text=chunk_text,
                summary=summary,
                keywords=keywords,
                confidence=0.9
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response was: {response[:200]}")
            return self._fallback_summary(chunk_text)
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
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
