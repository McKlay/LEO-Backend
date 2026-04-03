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
    original_language: str = Field(
        default="en",
        description="Detected language of user query: en, fil, ceb, or mixed"
    )
    normalized_query_en: str = Field(
        default="",
        description="English normalized query for retrieval"
    )
    needs_clarification: bool = Field(
        description="Whether the query is too vague and needs clarification"
    )
    clarification_question: Optional[str] = Field(
        default=None,
        description="Single best clarifying question in user's original language"
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
    out_of_scope: bool = Field(
        default=False,
        description="Whether the query is outside the Philippine labor law domain"
    )
    out_of_scope_message: Optional[str] = Field(
        default=None,
        description="Friendly redirect message in user's language when query is out of scope"
    )
    is_meta_conversational: bool = Field(
        default=False,
        description=(
            "True when the turn is purely a social/session-management exchange "
            "(greeting, thanks, farewell, acknowledgement, conversation summary, "
            "bot capability question) with NO new information need. "
            "Retrieval is skipped when this is True."
        )
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
        
        logger.info(
            f"Query analysis pipeline initialized: "
            f"enabled={self.enabled}, "
            f"smart_clarification={self.smart_clarification_enabled}"
        )
    
    async def analyze(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        preferred_language: Optional[str] = None
    ) -> QueryAnalysis:
        """
        Analyze a user query with context awareness.
        
        Args:
            query: User's query text
            conversation_history: Previous messages for context (optional)
            preferred_language: Preferred response language from request (en, fil, ceb)
            
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
            messages = self._build_analysis_prompt(
                query=query,
                conversation_history=conversation_history,
                preferred_language=preferred_language
            )
            logger.info(
                "Query analysis request prepared: "
                f"preferred_language={preferred_language or 'auto'}, "
                f"history_count={len(conversation_history) if conversation_history else 0}, "
                f"query_len={len(query)}"
            )
            
            # Call LLM with timeout using specialized analyze_query method
            try:
                response = await asyncio.wait_for(
                    self.llm.analyze_query(
                        messages=messages,
                        temperature=0.1,  # Very low temp for structured analysis
                        max_tokens=settings.query_analysis_max_tokens
                    ),
                    timeout=self.analysis_timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"Query analysis timed out after {self.analysis_timeout}s")
                return await self._fallback_analysis(query)
            
            # Parse JSON response
            analysis_data = self._parse_llm_response(response.content)
            logger.info(
                "Parsed query analysis payload: "
                f"original_language={analysis_data.get('original_language')}, "
                f"needs_clarification={analysis_data.get('needs_clarification')}, "
                f"out_of_scope={analysis_data.get('out_of_scope')}, "
                f"out_of_scope_message={analysis_data.get('out_of_scope_message')}, "
                f"is_meta_conversational={analysis_data.get('is_meta_conversational')}, "
                f"concepts={len(analysis_data.get('legal_concepts', []))}, "
                f"keywords={len(analysis_data.get('keywords', []))}"
            )
            
            # Create QueryAnalysis object
            analysis = QueryAnalysis(**analysis_data)

            # Ensure normalized query is always populated for retrieval.
            if not analysis.normalized_query_en:
                analysis.normalized_query_en = query

            if not analysis.needs_clarification:
                analysis.clarification_question = None

            if preferred_language and analysis.needs_clarification:
                logger.info(
                    "Clarification language trace: "
                    f"preferred={preferred_language}, detected_original={analysis.original_language}, "
                    f"question_preview={repr((analysis.clarification_question or '')[:120])}"
                )
            
            # Enhance with regex-based article extraction
            articles = self._extract_articles_regex(query)
            if articles:
                analysis.articles.extend(articles)
                analysis.articles = list(set(analysis.articles))  # Deduplicate
            
            logger.info(
                f"Query analysis complete: "
                f"needs_clarification={analysis.needs_clarification}, "
                f"out_of_scope={analysis.out_of_scope}, "
                f"is_meta_conversational={analysis.is_meta_conversational}, "
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
        conversation_history: Optional[List[Dict[str, Any]]],
        preferred_language: Optional[str] = None
    ) -> List[Message]:
        """
        Build LLM prompt for query analysis with conversation context.
        
        Args:
            query: Current user query
            conversation_history: Previous messages for context
            preferred_language: Preferred response language from request (en, fil, ceb)
            
        Returns:
            List of messages for LLM
        """
        # Build conversation context string
        context_str = ""
        has_context = False
        
        if conversation_history and len(conversation_history) > 0:
            # NOTE: conversation_history already excludes the current query being analyzed
            # (it's retrieved BEFORE adding the current message in chat_orchestrator)
            # So we should NOT exclude the last message - it's the previous exchange.
            
            # Take up to the last 6 messages (3 exchanges)
            relevant_history = conversation_history[-6:] if conversation_history else []
            
            if relevant_history:
                has_context = True
                context_lines = []
                for msg in relevant_history:
                    role = msg.get("role", "unknown")
                    content = (msg.get("content") or msg.get("text") or "")[:300]
                    context_lines.append(f"{role.upper()}: {content}")
                context_str = "\n".join(context_lines)
        
        if has_context:
            context_section = f"Previous conversation:\n{context_str}\n\n"
        else:
            context_section = "This is the first query in the conversation.\n\n"

        if preferred_language in {"en", "fil", "ceb"}:
            clarification_lang_instruction = (
                f"Write clarification_question in: {preferred_language}."
            )
        else:
            clarification_lang_instruction = (
                "Write clarification_question in the same language as the user's latest message."
            )

        system_prompt = f"""You analyze user queries for a Philippine labor-law RAG pipeline.
{context_section}
===STEP 1 — META-CONVERSATIONAL GATE===
If the query is purely conversational with NO new information request, mark as meta-conversational:
  • Greetings, thanks, farewells, acknowledgements ("hi", "salamat", "okay", "bye")
  • Requests to summarize/recap the conversation
  • Questions about bot capabilities

Mixed turns (greeting + new question) are NOT meta-conversational.

If meta-conversational: set is_meta_conversational=true, out_of_scope=false, needs_clarification=false, all arrays empty, normalized_query_en="". Stop here.

===STEP 2 — DOMAIN SCOPE CHECK===
Only handle Philippine labor law: employment, termination, wages, overtime, benefits, DOLE, SSS/PhilHealth/Pag-IBIG, safety.

If out of scope: set out_of_scope=true, write out_of_scope_message in user's language identifying system as LEO, set all other fields empty/false.

===STEP 3 — QUERY ANALYSIS===
🚨 CRITICAL: If the assistant ALREADY ASKED a clarification question and the user is RESPONDING to it, the ambiguity is RESOLVED. Set needs_clarification=false and proceed with analysis.

Tasks:
1) Always consolidate follow-ups and multi-turn queries with conversation context (include prior context in legal_concepts/keywords)
2) Extract: language (en/fil/ceb/mixed), legal concepts, explicit article references
3) Produce normalized_query_en: Complete self-contained English query merging full conversation intent.
   Example: "May karapatan sa separation pay?" + answer "serious misconduct, regular, 3 yrs" → "Is a regular employee with 3 years entitled to separation pay after dismissal for serious misconduct?"
4) Determine if clarification needed

When to clarify (ONLY if no prior clarification exchange):
  ✓ Missing region for minimum wage lookup
  ✓ Holiday type unspecified for pay computation
  ✓ Employment status unknown when it changes the rule
  ✓ First-turn vague query with zero details ("what are my rights?")
  ✓ Only described a specific scenario without asking a clear question ("I was terminated for absenteeism")
  ✓ Scenario where multiple legal interpretations are possible and user didn't specify which angle they're asking about ("I want to resign, what benefits can I get?" — clarify if they mean "what benefits do I lose?" or "what benefits am I entitled to?")
  ✓ When the query is about employee compensation or benefits and the user hasn't specified key details that would affect the answer (e.g. "How much severance pay do I get?" → clarify about years of service, employment type, reason for termination, severity of accident, etc.)
  ✓ When it comes to labor_relations topics, clarify vague collective action intent (union vs. complaint vs. strike) since it requires clarification before mapping to ULP and right to self-organization provisions
  ✓ When query is about contractor liability, clarify nature of contractor relationship and work since it affects which provisions apply

When NOT to clarify:
  ✗ User responding to assistant's prior clarification question
  ✗ Query has legally specific terms ("without just cause", "constructive dismissal", "retrenchment")
  ✗ Context resolves pronouns/follow-ups
  ✗ Specific scenario stated ("I was terminated", "not paying overtime")

Clarification format: ONE topic-guiding question in user's language. {clarification_lang_instruction}

Keyword rules:
- Extract 2-4 SPECIFIC, DISTINCTIVE terms only
- NEVER extract: "Philippines", "Philippine", "labor law", "Labor Code", "worker", "employee", "employer"
- Extract: specific benefits ("13th month", "SIL"), procedures ("retrenchment"), regions ("NCR"), article numbers

Return JSON (no markdown):
{{
    "original_language": "en|fil|ceb|mixed",
    "normalized_query_en": "Complete English query merging conversation intent (not just current message translation)",
    "is_meta_conversational": false,
    "out_of_scope": false,
    "out_of_scope_message": null,
    "needs_clarification": false,
    "clarification_question": null,
    "legal_concepts": ["..."],
    "articles": ["Article 297"],
    "keywords": ["..."]
}}"""

        user_prompt = f"Analyze this query: \"{query}\""
        
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt)
        ]
        
        logger.info(
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

            if "normalized_query_en" not in data or not isinstance(data.get("normalized_query_en"), str):
                data["normalized_query_en"] = ""

            if "original_language" not in data or not isinstance(data.get("original_language"), str):
                data["original_language"] = "en"

            if "clarification_question" not in data:
                data["clarification_question"] = None

            # Out-of-scope fields
            if "out_of_scope" not in data or not isinstance(data.get("out_of_scope"), bool):
                data["out_of_scope"] = False
            if "out_of_scope_message" not in data:
                data["out_of_scope_message"] = None

            # Meta-conversational field
            if "is_meta_conversational" not in data or not isinstance(data.get("is_meta_conversational"), bool):
                data["is_meta_conversational"] = False

            # Mutual exclusivity: a turn cannot be both out-of-scope and meta-conversational
            if data.get("out_of_scope"):
                data["is_meta_conversational"] = False

            # When out of scope, enforce consistent state
            if data.get("out_of_scope"):
                data["needs_clarification"] = False
                data["clarification_question"] = None
                data["legal_concepts"] = []
                data["articles"] = []
                data["keywords"] = []
                data["normalized_query_en"] = ""
                # If LLM forgot to include the message, use a sensible default
                if not data.get("out_of_scope_message"):
                    data["out_of_scope_message"] = (
                        "I'm LEO, your Philippine labor law assistant. "
                        "I can only help with labor law questions — feel free to ask about "
                        "wages, termination, benefits, DOLE, and more!"
                    )

            # When meta-conversational, enforce consistent state (no retrieval signals needed)
            if data.get("is_meta_conversational"):
                data["needs_clarification"] = False
                data["clarification_question"] = None
                data["legal_concepts"] = []
                data["articles"] = []
                data["keywords"] = []
                data["normalized_query_en"] = ""
            
            # Ensure lists exist
            for key in ["legal_concepts", "articles", "keywords"]:
                if key not in data or not isinstance(data[key], list):
                    data[key] = []

            # If LLM says clarification needed but omitted the question,
            # treat it as no clarification needed rather than using a hardcoded fallback.
            if data.get("needs_clarification") and not data.get("clarification_question"):
                logger.warning(
                    "LLM set needs_clarification=true but provided no clarification_question; "
                    "treating as needs_clarification=false to avoid hardcoded fallback."
                )
                data["needs_clarification"] = False

            if not data.get("needs_clarification"):
                data["clarification_question"] = None
            
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
        - "Department Order 147-15"
        - "DOLE Department Order 147-15"
        - "DO 147-15"
        
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

        # Pattern for Department Orders: "DOLE Department Order 147-15",
        # "Department Order 147-15", or "DO 147-15".
        # Canonical output form: "Department Order N-NN".
        do_pattern = r'\b(?:DOLE\s+)?Department\s+Order\s+([\d]+-[\w]+)\b'
        matches = re.finditer(do_pattern, query, re.IGNORECASE)
        for match in matches:
            articles.append(f"Department Order {match.group(1)}")

        do_abbrev_pattern = r'\bDO\s+([\d]+-[\w]+)\b'
        matches = re.finditer(do_abbrev_pattern, query, re.IGNORECASE)
        for match in matches:
            articles.append(f"Department Order {match.group(1)}")
        
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
        
        return QueryAnalysis(
            original_language="en",
            normalized_query_en=query,
            needs_clarification=needs_clarification and self.smart_clarification_enabled,
            clarification_question=None,
            legal_concepts=[],
            articles=articles,
            keywords=keywords
        )
    
    async def analyze_query(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        preferred_language: Optional[str] = None
    ) -> QueryAnalysis:
        """
        Alias for analyze() method for backward compatibility.
        
        Args:
            query: User's query text
            conversation_history: Previous messages for context (optional)
            preferred_language: Preferred response language from request (en, fil, ceb)
            
        Returns:
            QueryAnalysis with structured analysis results
        """
        return await self.analyze(query, conversation_history, preferred_language)
