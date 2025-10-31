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
        """Get default system prompt template."""
        return """You are LEO, a specialized chatbot assistant for Philippine labor law.

Your role is to provide accurate, helpful information about Philippine labor laws and regulations based ONLY on the provided context.

Guidelines:
1. Answer ONLY using information from the provided context
2. If the context doesn't contain enough information, say so clearly
3. Always cite your sources using [1], [2], etc. format
4. Be precise and avoid speculation
5. Use clear, professional language
6. If asked about topics outside Philippine labor law, politely redirect

Current date: {current_date}
User language preference: {language}

Context from Philippine Labor Law knowledge base:
{context}

Please answer the user's question based on the above context."""
    
    def build_grounded_prompt(
        self,
        query: str,
        context_results: List[QueryResult],
        language: str = "en",
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> List[Dict[str, str]]:
        """
        Build a grounded prompt with context and citations.
        
        Args:
            query: User query
            context_results: Retrieved context from vector store
            language: User's language preference
            conversation_history: Previous conversation messages
            
        Returns:
            List of messages for LLM (system + history + user)
        """
        # Format context with citations
        formatted_context = self._format_context_with_citations(context_results)
        
        # Truncate if needed
        if len(formatted_context) > self.max_context_length:
            formatted_context = formatted_context[:self.max_context_length] + "..."
            logger.warning(f"Context truncated to {self.max_context_length} chars")
        
        # Build system prompt
        system_prompt = self.system_prompt_template.format(
            current_date=datetime.now().strftime("%Y-%m-%d"),
            language=self._get_language_name(language),
            context=formatted_context
        )
        
        # Build message list
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history if provided
        if conversation_history:
            messages.extend(conversation_history)
        
        # Add current user query
        messages.append({"role": "user", "content": query})
        
        logger.debug(f"Built grounded prompt with {len(context_results)} context chunks")
        
        return messages
    
    def _format_context_with_citations(self, results: List[QueryResult]) -> str:
        """
        Format context results with citation markers.
        
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
    
    def extract_citation_metadata(
        self,
        results: List[QueryResult]
    ) -> List[Dict[str, Any]]:
        """
        Extract structured citation metadata for API response.
        
        Args:
            results: List of query results
            
        Returns:
            List of citation metadata dictionaries
        """
        citations = []
        for idx, result in enumerate(results, 1):
            metadata = result.metadata or {}
            
            citation = {
                "id": idx,
                "citation_key": f"[{idx}]",
                "source": metadata.get("source", "Unknown Source"),
                "section": metadata.get("section"),
                "article": metadata.get("article"),
                "url": metadata.get("url"),
                "relevance_score": round(result.score, 3),
                "content_preview": result.content[:200] + "..." if len(result.content) > 200 else result.content
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
