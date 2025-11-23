"""
Grounding pipeline module for context validation and citation extraction.

Ensures LLM responses are grounded in retrieved context with proper citations.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime

from core import get_logger
from adapters.vectorstore.base import QueryResult


logger = get_logger(__name__)


class GroundingPipeline:
    """
    Handles context validation and citation grounding for LLM responses.
    
    Ensures generated responses stay grounded in retrieved knowledge
    and include proper citations.
    """
    
    def __init__(
        self,
        system_prompt_template: Optional[str] = None,
        max_context_length: int = 8000
    ):
        """
        Initialize grounding pipeline.
        
        Args:
            system_prompt_template: Template for system prompt
            max_context_length: Maximum context length in characters
        """
        self.max_context_length = max_context_length
        self.system_prompt_template = system_prompt_template or self._default_system_prompt()
        
        logger.info(f"Grounding pipeline initialized (max_context={max_context_length})")
    
    def _default_system_prompt(self) -> str:
        """
        Get optimized system prompt for GPT-4 Turbo single-step grounding.
        
        Key Design Decisions:
        - Concise structure to minimize noise (GPT-4 handles legal complexity well)
        - Emphasizes conversational tone and empathy (labor law is emotionally charged)
        - Natural citation integration instructions (avoid robotic "According to...")
        - Clear boundary enforcement (Philippine labor law only)
        - Examples-based guidance for tone consistency
        """
        return """You are LEO, a knowledgeable and empathetic Philippine labor law assistant.

**Core Principles**:
1. Ground ALL answers in the provided legal context - never speculate
2. Integrate citations naturally within explanations (e.g., "Employers must pay 13th month pay by December 24 (PD 851, Sec 1)...")
3. Use warm, conversational tone while maintaining legal precision
4. For sensitive topics (dismissal, harassment), acknowledge emotions with empathy
5. Provide actionable guidance when relevant

**Response Format**:
- Opening: Acknowledge the question warmly
- Body: Explain the law clearly with natural citations
- Closing: Summarize key points and suggest next steps if applicable

**Citation Style**: Integrate inline, not as headers. Example: "The law requires..." NOT "According to Article X..."

**If Insufficient Context**: Politely state what you can answer and what you cannot based on available information.

**Out-of-Scope**: For non-labor law topics, politely redirect: "I specialize in Philippine labor law. For [topic], I recommend..."

Current date: {current_date}
Language: {language}

---

**Legal Sources Available**:
{context}

---"""
    
    def build_grounded_prompt(
        self,
        query: str,
        context_results: List[QueryResult],
        language: str = "en",
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> List[Dict[str, str]]:
        """
        Build a grounded prompt with rich context for single-step GPT-4 generation.
        
        Optimization Strategy:
        - Use FULL document text (not snippets) for better context
        - Format hierarchically (source → article → content)
        - Keep context concise but complete (target: 2000-3000 tokens)
        - Conversation history limited to last 3 exchanges (600-800 tokens)
        - Total prompt budget: ~4000 tokens (leaves 4000+ for response)
        
        Args:
            query: User query
            context_results: Retrieved context from vector store
            language: User's language preference
            conversation_history: Previous conversation messages
            
        Returns:
            List of messages for LLM (system + history + user)
        """
        # Format context with full documents (optimized for readability)
        formatted_context = self._format_rich_context(context_results)
        
        # Smart truncation: Keep most relevant, remove least relevant if needed
        if len(formatted_context) > self.max_context_length:
            logger.warning(
                f"Context exceeds {self.max_context_length} chars "
                f"({len(formatted_context)} chars), truncating intelligently"
            )
            formatted_context = self._smart_truncate_context(
                context_results,
                max_length=self.max_context_length
            )
        
        # Build system prompt
        system_prompt = self.system_prompt_template.format(
            current_date=datetime.now().strftime("%B %d, %Y"),
            language=self._get_language_name(language),
            context=formatted_context
        )
        
        # Build message list
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history if provided (limit to last 3 exchanges = 6 messages)
        if conversation_history:
            # Take only last 3 user-assistant exchanges for context efficiency
            recent_history = conversation_history[-6:]  # Last 3 exchanges
            messages.extend(recent_history)
            
            logger.debug(
                f"Added {len(recent_history)} messages from conversation history "
                f"(limited to last 3 exchanges)"
            )
        
        # Add current user query
        messages.append({"role": "user", "content": query})
        
        logger.debug(
            f"Built grounded prompt: {len(context_results)} documents, "
            f"{len(messages)} total messages, "
            f"system_prompt={len(system_prompt)} chars"
        )
        
        return messages
    
    def _format_context_with_citations(self, results: List[QueryResult]) -> str:
        """
        Format context results with citation markers (LEGACY - kept for compatibility).
        
        Args:
            results: List of query results
            
        Returns:
            Formatted context string
        """
        if not results:
            return "No relevant context available."
        
        context_parts = []
        for idx, result in enumerate(results, 1):
            # Extract metadata
            source = result.metadata.get("source", "Unknown Source")
            section = result.metadata.get("section", "")
            
            # Build citation header
            citation = f"[{idx}] Source: {source}"
            if section:
                citation += f" | Section: {section}"
            citation += f" | Relevance: {result.score:.2f}"
            
            # Add content
            context_parts.append(
                f"{citation}\n{result.content.strip()}\n"
            )
        
        return "\n---\n".join(context_parts)
    
    def _format_rich_context(self, results: List[QueryResult]) -> str:
        """
        Format context with full documents in hierarchical structure.
        
        Optimized for GPT-4 comprehension:
        - Clear source attribution
        - Article/section hierarchy
        - Full text (not fragments)
        - Concise but complete
        
        Args:
            results: List of query results
            
        Returns:
            Formatted rich context string
        """
        if not results:
            return "No relevant legal sources found for this query."
        
        context_parts = []
        
        for idx, result in enumerate(results, 1):
            metadata = result.metadata or {}
            
            # Extract metadata
            source = metadata.get("source", "Labor Code of the Philippines")
            article = metadata.get("article", metadata.get("section", f"Document {idx}"))
            title = metadata.get("title", "")
            
            # Build hierarchical header
            header = f"**[{idx}] {source}"
            if article:
                header += f" - {article}"
            if title:
                header += f": {title}"
            header += "**"
            
            # Add full content
            content = result.content.strip()
            
            # Format document block
            doc_block = f"{header}\n\n{content}"
            
            context_parts.append(doc_block)
        
        # Join with clear separators
        formatted = "\n\n---\n\n".join(context_parts)
        
        logger.debug(
            f"Formatted {len(results)} documents into rich context "
            f"({len(formatted)} chars)"
        )
        
        return formatted
    
    def _smart_truncate_context(
        self,
        results: List[QueryResult],
        max_length: int
    ) -> str:
        """
        Intelligently truncate context while preserving most relevant documents.
        
        Strategy:
        - Sort by relevance score (keep highest scoring documents)
        - Truncate least relevant documents first
        - Ensure at least top 3 documents are included fully
        
        Args:
            results: List of query results (assumed sorted by score)
            max_length: Maximum context length in characters
            
        Returns:
            Truncated formatted context
        """
        if not results:
            return "No relevant context available."
        
        # Sort by score descending (highest relevance first)
        sorted_results = sorted(results, key=lambda r: r.score, reverse=True)
        
        # Try to fit as many full documents as possible
        context_parts = []
        current_length = 0
        
        for idx, result in enumerate(sorted_results, 1):
            metadata = result.metadata or {}
            source = metadata.get("source", "Labor Code")
            article = metadata.get("article", f"Doc {idx}")
            
            # Format this document
            header = f"**[{idx}] {source} - {article}**"
            content = result.content.strip()
            doc_block = f"{header}\n\n{content}"
            doc_length = len(doc_block) + 6  # +6 for separator
            
            # Check if we can fit this document
            if current_length + doc_length <= max_length:
                context_parts.append(doc_block)
                current_length += doc_length
            else:
                # Truncate this document if it's still early in the list
                if idx <= 3:  # Ensure at least top 3 are included
                    remaining = max_length - current_length - len(header) - 50
                    if remaining > 200:  # Only truncate if we can fit meaningful content
                        truncated_content = content[:remaining] + "... [truncated]"
                        doc_block = f"{header}\n\n{truncated_content}"
                        context_parts.append(doc_block)
                        current_length = max_length
                break  # Stop adding more documents
        
        formatted = "\n\n---\n\n".join(context_parts)
        
        logger.info(
            f"Smart truncation: kept {len(context_parts)}/{len(results)} documents "
            f"({len(formatted)}/{max_length} chars)"
        )
        
        return formatted
    
    def extract_citation_metadata(
        self,
        results: List[QueryResult]
    ) -> List[Dict[str, Any]]:
        """
        Extract structured citation metadata for API response.
        
        Args:
            results: List of query results
            
        Returns:
            List of citation metadata dictionaries matching API spec
        """
        import uuid
        citations = []
        for idx, result in enumerate(results, 1):
            metadata = result.metadata or {}
            
            # Map metadata fields from vector store to API response format
            # Handle both 'sections' and 'chunks' table schemas
            article_id = (
                metadata.get("article_number") or 
                metadata.get("_parent_article") or 
                metadata.get("article") or 
                "N/A"
            )
            
            title = (
                metadata.get("article_title") or 
                metadata.get("_parent_title") or 
                metadata.get("title") or 
                "Labor Law Provision"
            )
            
            # Extract text excerpt (limited to 300 chars)
            excerpt = result.content[:300] + "..." if len(result.content) > 300 else result.content
            
            # Get source info (use source_url from JOIN with labor_law_sources table)
            source_title = metadata.get("source_title", "Labor Code of the Philippines")
            source_url = metadata.get("source_url") or metadata.get("url", "https://www.dole.gov.ph/labor-code/")
            
            # Build citation matching API specification (schemas_chat.py Citation model)
            # Required fields: id, text, source, article, url, confidence
            citation = {
                "id": str(uuid.uuid4()),
                "text": excerpt,  # API expects 'text' field
                "source": source_title,
                "article": article_id,  # API expects 'article' field (not 'article_id')
                "url": source_url,  # Use actual source URL from labor_law_sources table
                "confidence": round(result.score, 3)
            }
            
            citations.append(citation)
        
        return citations
    
    def validate_grounding(
        self,
        response: str,
        context_results: List[QueryResult]
    ) -> Dict[str, Any]:
        """
        Validate that response is properly grounded in context.
        
        Args:
            response: LLM generated response
            context_results: Context that was provided
            
        Returns:
            Validation results with metrics
        """
        # Check for citation markers
        citation_count = sum(
            1 for i in range(1, len(context_results) + 1)
            if f"[{i}]" in response
        )
        
        # Check response length
        response_length = len(response.split())
        
        # Basic heuristics
        is_grounded = citation_count > 0
        has_disclaimer = any(
            phrase in response.lower()
            for phrase in ["i cannot", "not enough information", "context does not"]
        )
        
        validation = {
            "is_grounded": is_grounded,
            "citation_count": citation_count,
            "total_sources": len(context_results),
            "response_word_count": response_length,
            "has_disclaimer": has_disclaimer,
            "grounding_score": citation_count / max(len(context_results), 1)
        }
        
        logger.debug(f"Grounding validation: {validation}")
        
        return validation
    
    def _get_language_name(self, code: str) -> str:
        """Convert language code to full name."""
        language_names = {
            "en": "English",
            "fil": "Filipino (Tagalog)",
            "ceb": "Cebuano"
        }
        return language_names.get(code, "English")
    
    def add_disclaimer(self, response: str, language: str = "en") -> str:
        """
        Add legal disclaimer to response.
        
        Args:
            response: Generated response
            language: Language code
            
        Returns:
            Response with disclaimer appended
        """
        disclaimers = {
            "en": "\n\n---\n**Disclaimer**: This information is for general guidance only and does not constitute legal advice. For specific legal concerns, please consult with a qualified labor law attorney.",
            "fil": "\n\n---\n**Paalala**: Ang impormasyong ito ay para sa pangkalahatang gabay lamang at hindi legal na payo. Para sa partikular na legal na usapin, makipag-ugnayan sa isang kwalipikadong abogado.",
            "ceb": "\n\n---\n**Pahinumdom**: Kining impormasyon alang sa kinatibuk-ang giya lamang ug dili legal nga tambag. Para sa piho nga legal nga mga kabalaka, pakigsulti sa usa ka kwalipikado nga abogado."
        }
        
        disclaimer = disclaimers.get(language, disclaimers["en"])
        return response + disclaimer
