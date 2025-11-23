"""
Query analysis pipeline with smart clarification detection.

Uses GPT-4o-mini for intelligent query analysis, clarification detection,
and concept extraction to optimize retrieval strategies.
"""
import re
import json
import asyncio
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from core import get_logger, AppError, settings
from adapters.llm.base import BaseLLM, Message

logger = get_logger(__name__)


class QueryAnalysis(BaseModel):
    """
    Structured query analysis result.
    
    Contains clarification status, extracted concepts, articles,
    and keywords for optimized retrieval routing.
    """
    needs_clarification: bool = Field(
        description="Whether the query is too vague and needs clarification"
    )
    clarification_reason: Optional[str] = Field(
        default=None,
        description="Explanation of why clarification is needed"
    )
    clarification_questions: Optional[List[str]] = Field(
        default=None,
        description="Specific follow-up questions to ask (3-4 questions)"
    )
    suggested_topics: Optional[List[str]] = Field(
        default=None,
        description="Topic suggestions for multi-choice clarification"
    )
    legal_concepts: List[str] = Field(
        default_factory=list,
        description="Extracted legal concepts from query"
    )
    articles: List[str] = Field(
        default_factory=list,
        description="Extracted article numbers or legal citations"
    )
    keywords: List[str] = Field(
        default_factory=list,
        description="Key terms for keyword-based retrieval"
    )
    query_type: str = Field(
        default="general",
        description="Type of query: specific, general, procedural, etc."
    )
    breadth: str = Field(
        default="narrow",
        description="Query breadth: narrow, medium, broad"
    )


class QueryAnalysisPipeline:
    """
    Query analysis pipeline with smart clarification detection.
    
    Analyzes user queries using GPT-4o-mini to:
    - Detect vague queries that need clarification
    - Generate specific, helpful follow-up questions
    - Extract legal concepts and article references
    - Extract keywords for retrieval
    - Provide context-aware analysis using conversation history
    """
    
    def __init__(self, llm: BaseLLM):
        """
        Initialize query analysis pipeline.
        
        Args:
            llm: LLM adapter for query analysis (should use GPT-4o-mini)
        """
        self.llm = llm
        self.enabled = settings.enable_query_analysis
        self.smart_clarification_enabled = settings.enable_smart_clarification
        self.analysis_timeout = settings.analysis_timeout
        self.max_clarification_questions = settings.max_clarification_questions
        
        logger.info(
            f"Query analysis pipeline initialized: "
            f"enabled={self.enabled}, "
            f"smart_clarification={self.smart_clarification_enabled}"
        )
    
    async def analyze(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> QueryAnalysis:
        """
        Analyze a user query with context awareness.
        
        Args:
            query: User's query text
            conversation_history: Previous messages for context (optional)
            
        Returns:
            QueryAnalysis with structured analysis results
            
        Raises:
            AppError: If analysis fails
        """
        if not self.enabled:
            # Return basic analysis without LLM call
            return await self._fallback_analysis(query)
        
        try:
            logger.info(f"Analyzing query: '{query[:100]}...'")
            
            # Build analysis prompt with conversation context
            messages = self._build_analysis_prompt(query, conversation_history)
            
            # Call LLM with timeout using specialized analyze_query method
            try:
                response = await asyncio.wait_for(
                    self.llm.analyze_query(
                        messages=messages,
                        temperature=0.1,  # Very low temp for structured analysis
                        max_tokens=500  # Compact JSON response
                    ),
                    timeout=self.analysis_timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"Query analysis timed out after {self.analysis_timeout}s")
                return await self._fallback_analysis(query)
            
            # Parse JSON response
            analysis_data = self._parse_llm_response(response.content)
            
            # Create QueryAnalysis object
            analysis = QueryAnalysis(**analysis_data)

            # Post-processing: override LLM clarification decision when there
            # are strong, unambiguous topic signals in the query or in the
            # extracted analysis. This is a lightweight, deterministic
            # guard to reduce false-positive clarification for clearly
            # scoped legal questions (e.g. "What is the minimum wage?").
            #
            # IMPORTANT: We do not modify the analysis prompt here per
            # request; instead we apply a small heuristic after the LLM
            # returns. This keeps the LLM prompt intact while avoiding
            # overly-strict clarification behavior.
            if analysis.needs_clarification:
                qlower = query.lower()
                topic_keywords = [
                    "minimum wage", "wage", "overtime", "13th month",
                    "maternity", "termination", "severance", "contractual",
                    "holiday pay", "sick leave", "hazard pay", "probation"
                ]

                keywords_in_analysis = [k.lower() for k in analysis.keywords or []]
                legal_concepts_lower = [c.lower() for c in analysis.legal_concepts or []]

                has_strong_topic = (
                    any(k in qlower for k in topic_keywords)
                    or bool(analysis.articles)
                    or any(k in kw for kw in keywords_in_analysis for k in ["wage", "overtime", "minimum", "13th", "maternity", "termination"]) 
                    or any(k in lc for lc in legal_concepts_lower for k in ["wage", "overtime", "minimum", "maternity", "termination"]) 
                )

                if has_strong_topic:
                    logger.info("Overriding LLM clarification decision based on strong topic signals")
                    analysis.needs_clarification = False
                    analysis.clarification_reason = None
                    analysis.clarification_questions = []
            
            # Enhance with regex-based article extraction
            articles = self._extract_articles_regex(query)
            if articles:
                analysis.articles.extend(articles)
                analysis.articles = list(set(analysis.articles))  # Deduplicate
            
            logger.info(
                f"Query analysis complete: "
                f"needs_clarification={analysis.needs_clarification}, "
                f"articles={len(analysis.articles)}, "
                f"concepts={len(analysis.legal_concepts)}"
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Query analysis error: {str(e)}", exc_info=True)
            # Don't fail the entire pipeline - use fallback
            return await self._fallback_analysis(query)
    
    def _build_analysis_prompt(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, Any]]]
    ) -> List[Message]:
        """
        Build LLM prompt for query analysis with conversation context.
        
        Args:
            query: Current user query
            conversation_history: Previous messages for context
            
        Returns:
            List of messages for LLM
        """
        # Build conversation context string
        context_str = ""
        has_context = False
        if conversation_history and len(conversation_history) > 0:
            # Exclude the current user message (last message) since it's already being analyzed
            # Take up to the last 6 messages (3 exchanges) before the current query
            relevant_history = conversation_history[:-1][-6:] if len(conversation_history) > 1 else []
            
            if relevant_history:
                has_context = True
                context_lines = []
                for msg in relevant_history:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")[:300]  # Increased truncation limit
                    context_lines.append(f"{role.upper()}: {content}")
                context_str = "\n".join(context_lines)
        
        if has_context:
            context_section = f"Previous conversation:\n{context_str}\n\n"
            clarification_rules = """CRITICAL CLARIFICATION RULES:
- **NEVER clarify** if query references conversation context (e.g., "How often is it updated?", "What about that?", "Tell me more")
- **NEVER clarify** pronouns ("it", "they", "that") when previous context exists
- **DO clarify** only if BOTH conditions: (1) vague query AND (2) NO relevant context in conversation
- **NO clarify** for: follow-ups, pronoun references with context, topic continuations

CLARIFY ONLY if: First query AND vague ("my rights"), no context AND ambiguous ("they"), standalone unclear question
"""
        else:
            context_section = "This is the first query in the conversation.\n\n"
            clarification_rules = """CLARIFICATION RULES:
CLARIFY if: vague ("my rights"), ambiguous pronouns without context ("they"), no specific topic ("I have problem")
NO CLARIFY if: specific topic, article reference, clear legal concept
"""
        
        system_prompt = f"""Analyze Philippine labor law query. {context_section}{clarification_rules}

Return JSON only:
{{
  "needs_clarification": bool,
  "clarification_reason": "why" (if true),
  "clarification_questions": ["specific Q1", "Q2", "Q3"] (if true, 3-4 questions),
  "suggested_topics": ["topic1", "topic2"] (if true),
  "legal_concepts": ["concept1"],
  "articles": ["Article 123"],
  "keywords": ["key1", "key2"],
  "query_type": "specific|general|procedural|rights|benefits",
  "breadth": "narrow|medium|broad"
}}"""

        user_prompt = f"Analyze this query: \"{query}\""
        
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt)
        ]
        
        logger.debug(
            f"Query analysis prompt built: has_context={has_context}, "
            f"history_messages={len(conversation_history) if conversation_history else 0}"
        )
        
        return messages
    
    def _parse_llm_response(self, response_content: str) -> Dict[str, Any]:
        """
        Parse LLM JSON response with error handling.
        
        Args:
            response_content: LLM response text
            
        Returns:
            Parsed JSON data
            
        Raises:
            AppError: If parsing fails
        """
        try:
            # Remove markdown code blocks if present
            content = response_content.strip()
            if content.startswith("```"):
                # Extract JSON from code block
                lines = content.split("\n")
                json_lines = []
                in_code = False
                for line in lines:
                    if line.startswith("```"):
                        in_code = not in_code
                        continue
                    if in_code or not line.startswith("```"):
                        json_lines.append(line)
                content = "\n".join(json_lines).strip()
            
            # Parse JSON
            data = json.loads(content)
            
            # Validate required fields
            if "needs_clarification" not in data:
                data["needs_clarification"] = False
            
            # Ensure lists exist
            for key in ["legal_concepts", "articles", "keywords"]:
                if key not in data or not isinstance(data[key], list):
                    data[key] = []
            
            # Limit clarification questions
            if data.get("clarification_questions"):
                data["clarification_questions"] = data["clarification_questions"][:self.max_clarification_questions]
            
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {str(e)}\nContent: {response_content[:500]}")
            raise AppError(
                message="Failed to parse query analysis response",
                error_code="QUERY_ANALYSIS_PARSE_ERROR",
                status_code=500,
                details={"error": str(e)}
            )
    
    def _extract_articles_regex(self, query: str) -> List[str]:
        """
        Extract article references using regex patterns.
        
        Supports patterns like:
        - "Article 123"
        - "Art. 123"
        - "PD 442"
        - "Presidential Decree 442"
        - "RA 10361"
        - "Republic Act 10361"
        
        Args:
            query: User query text
            
        Returns:
            List of extracted article references
        """
        articles = []
        
        # Pattern for "Article XXX" or "Art. XXX"
        article_pattern = r'\b(?:Article|Art\.?)\s+(\d+)\b'
        matches = re.finditer(article_pattern, query, re.IGNORECASE)
        for match in matches:
            articles.append(f"Article {match.group(1)}")
        
        # Pattern for "PD XXX" or "Presidential Decree XXX"
        pd_pattern = r'\b(?:PD|Presidential\s+Decree)\s+(\d+)\b'
        matches = re.finditer(pd_pattern, query, re.IGNORECASE)
        for match in matches:
            articles.append(f"PD {match.group(1)}")
        
        # Pattern for "RA XXX" or "Republic Act XXX"
        ra_pattern = r'\b(?:RA|Republic\s+Act)\s+(\d+)\b'
        matches = re.finditer(ra_pattern, query, re.IGNORECASE)
        for match in matches:
            articles.append(f"RA {match.group(1)}")
        
        return list(set(articles))  # Deduplicate
    
    async def _fallback_analysis(self, query: str) -> QueryAnalysis:
        """
        Fallback analysis when LLM is disabled or fails.
        
        Uses simple heuristics and regex patterns.
        
        Args:
            query: User query text
            
        Returns:
            Basic QueryAnalysis
        """
        logger.info("Using fallback query analysis")
        
        # Extract articles using regex
        articles = self._extract_articles_regex(query)
        
        # Simple keyword extraction (split and filter)
        words = query.lower().split()
        stop_words = {"the", "a", "an", "is", "are", "what", "how", "when", "where", "why", "can", "do", "does"}
        keywords = [w.strip("?,!.") for w in words if w not in stop_words and len(w) > 3][:10]
        
        # Detect vague queries using simple heuristics
        vague_indicators = [
            "my rights",
            "what about",
            "can they",
            "is this allowed",
            "problem at work",
            "help me"
        ]
        needs_clarification = any(indicator in query.lower() for indicator in vague_indicators)
        
        # Determine breadth
        if len(query.split()) <= 5:
            breadth = "narrow"
        elif len(query.split()) <= 15:
            breadth = "medium"
        else:
            breadth = "broad"
        
        return QueryAnalysis(
            needs_clarification=needs_clarification and self.smart_clarification_enabled,
            legal_concepts=[],
            articles=articles,
            keywords=keywords,
            query_type="general",
            breadth=breadth
        )
    
    async def analyze_query(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> QueryAnalysis:
        """
        Alias for analyze() method for backward compatibility.
        
        Args:
            query: User's query text
            conversation_history: Previous messages for context (optional)
            
        Returns:
            QueryAnalysis with structured analysis results
        """
        return await self.analyze(query, conversation_history)
