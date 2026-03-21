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
            # Exclude the current user message (last message) since it's already being analyzed
            # Take up to the last 6 messages (3 exchanges) before the current query
            relevant_history = conversation_history[:-1][-6:] if len(conversation_history) > 1 else []
            
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
===STEP 1 — META-CONVERSATIONAL GATE (evaluate this FIRST, before anything else)===
Some turns are about managing the conversation itself, not about seeking external information.
These are called meta-conversational intents and they are ALWAYS in-scope (out_of_scope=false).

A turn is meta-conversational if it falls into ANY of these categories:
  • Greetings / openings — e.g. "hi", "hello", "good morning", "kumusta"
  • Thanks / appreciation — e.g. "thank you", "thanks!", "salamat", "maraming salamat", "daghan kaayo"
  • Farewells — e.g. "goodbye", "bye", "take care"
  • Conversational acknowledgements — e.g. "okay", "got it", "I see", "makes sense", "alright", "perfect", "great"
  • Expressions of satisfaction or frustration about the chat — e.g. "that was helpful!", "this is confusing"
  • Requests to summarize, recap, or review the current conversation — e.g. "can you summarize our conversation?", "what did we discuss?", "recap everything"
  • Requests to clarify or expand on the assistant's previous answer — e.g. "what did you mean by that?", "can you explain that again?", "tell me more about that last point"
  • Questions about bot capabilities — e.g. "what can you do?", "what topics do you cover?"

CRITICAL GUARD — Mixed turns: A turn is meta-conversational ONLY if it contains NO new information request. If the query also asks a new question or references a specific labor law topic (even combined with a greeting, thanks, or acknowledgement), it is NOT meta-conversational — treat the entire turn as a regular query and continue to Step 2. Examples that are NOT meta-conversational: "okay got it, what about notice period?", "thanks! and how many days for resignation notice?", "tell me more about overtime pay".

RULE: If the query is purely meta-conversational (passes the guard above), you MUST set:
  - is_meta_conversational=true
  - out_of_scope=false
  - needs_clarification=false, clarification_question=null
  - legal_concepts=[], articles=[], keywords=[]
  - normalized_query_en="" (retrieval will be skipped — response uses conversation history only)
Do NOT check domain scope for these turns. Proceed directly to output.

===STEP 2 — DOMAIN SCOPE CHECK (only if NOT meta-conversational)===
This system ONLY handles Philippine labor law and directly related topics: employment relationships, termination/dismissal, wages, overtime pay, benefits (13th month, SIL, etc.), leave entitlements, DOLE procedures, labor disputes, collective bargaining, contracting/subcontracting, SSS/PhilHealth/Pag-IBIG contributions, and occupational safety.

If the query is clearly outside this scope (e.g., cooking recipes, weather forecast, coding/programming help, math problems, general trivia, foreign law, medical advice, personal finance unrelated to employment), set out_of_scope=true and write a short, friendly redirect message in the SAME LANGUAGE as the user's query. The message must identify the system as LEO — e.g. "Hi! I'm LEO, your Philippine labor law assistant. I can help with questions about wages, termination, benefits, DOLE, and other labor law topics. Feel free to ask!"

- When out_of_scope=true: set is_meta_conversational=false, needs_clarification=false, clarification_question=null, legal_concepts=[], articles=[], keywords=[], normalized_query_en="".
- When out_of_scope=false (the default for labor-related queries AND all meta-conversational intents): proceed with all tasks below.

Your task:
    1) If the query is a follow-up, first consolidate the user's full information need from recent dialogue.
    2) Detect ambiguity/underspecification.
    3) Extract legal concepts, keywords, and explicit legal references.
    4) Detect original language (en, fil, ceb, mixed).
    5) Produce normalized_query_en for retrieval (always English).

    Consolidation rule:
    - For follow-up or pronoun-heavy turns, infer the full intent from prior messages.
    - legal_concepts and keywords must represent the consolidated intent, not only the latest short utterance.
    - If the conversation history shows the assistant previously asked a clarification question, and the current user message is a direct response to that question, the ambiguity is RESOLVED. Consolidate the full context into a normalized query and set needs_clarification=false — do NOT ask another clarification.

Clarification policy:
- Ask clarification only when missing details materially change legal outcome.
- If context resolves pronouns/follow-up references, do not clarify.
- NEVER ask a second clarification if the user is directly responding to the assistant's prior clarification question — treat the response as resolving the ambiguity regardless of how brief it is.
- Legally specific terms carry sufficient legal meaning and do NOT require further specification: "without just cause" (= illegal dismissal, Art. 294), "constructive dismissal", "retrenchment", "redundancy", "closure", "disease termination", "forced resignation", "security of tenure".
- Typical clarification cases (ONLY when no prior exchange has already narrowed the topic): no region specified for a minimum wage rate lookup; holiday type completely unspecified for pay-rate computation; employment status entirely unknown and it changes the applicable rule; a bare vague complaint with zero factual detail and no prior exchange (e.g., first-turn "what are my rights?" alone).
- NOT clarification cases: user states a specific scenario in response to a prior clarification (e.g., "I was terminated without just cause", "my employer is not paying my overtime", "I was forced to resign"); query includes a legally defined term that is self-sufficient for retrieval.
- If no clarification is needed, set clarification_question to null.
- If clarification is needed, make ONE strong, topic-guiding question that is specific to Philippine labor law.
- The question should guide the user toward concrete issue categories when relevant (for example: termination, unpaid wages/overtime, benefits, leave, discrimination/harassment, contracting status).
- {clarification_lang_instruction}

Output requirements:
- Return strict JSON only. No markdown.
- Keep keywords concise and retrieval-oriented.
- Keep normalized_query_en short but complete.

Return JSON with this exact shape:
{{
    "original_language": "en|fil|ceb|mixed",
    "normalized_query_en": "english retrieval query",
    "is_meta_conversational": false,
    "out_of_scope": false,
    "out_of_scope_message": null,
    "needs_clarification": true,
    "clarification_question": "single follow-up question in the specified language",
    "legal_concepts": ["..."],
    "articles": ["Article 297", "RA 10361"],
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
