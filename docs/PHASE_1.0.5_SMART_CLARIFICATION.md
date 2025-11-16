# Smart LLM-Based Clarification Feature

**Status**: Approved for Phase 1.0.5  
**Date**: November 11, 2025  
**Related**: ADR-002, PHASE_1.0.5_ARCHITECTURE_REVISION.md

---

## Overview

Smart clarification leverages GPT-4o-mini's query analysis stage to intelligently detect vague queries and request specific follow-up information **before** executing the expensive retrieval and grounding pipeline.

---

## Problem Statement

### Current Deterministic Approach Limitations

The existing `is_clarification_needed()` method in `chat_orchestrator.py` uses rule-based heuristics:

```python
# Current approach (deterministic)
def is_clarification_needed(query: str) -> bool:
    # Rule-based checks:
    # - Query length < 5 words
    # - No question words (what, how, when, etc.)
    # - No specific legal terms
    return check_heuristics(query)
```

**Problems**:
1. **High false negative rate**: Misses nuanced vague queries
   - "What about my case?" (grammatically complete but contextually vague)
   - "Can they do this?" (pronouns without referents)
   - "I need help" (no question mark but clearly vague)

2. **Context-blindness**: Cannot handle multi-turn conversations
   - After "What is 13th month pay?", user asks "How is it calculated?"
   - Deterministic approach sees "it" as vague → false clarification request
   - User frustrated by unnecessary back-and-forth

3. **Language limitations**: Requires separate rules for each language
   - Filipino: "Ano ba yung karapatan ko?" 
   - Cebuano: "Unsa man akong katungod?"

4. **Generic clarifications**: When triggered, produces unhelpful generic response
   - "Could you please clarify your question?"
   - No specific guidance on what information is needed

---

## Solution: LLM-Based Smart Clarification

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│ Stage 1: Query Analysis + Clarification (GPT-4o-mini, 1.0s) │
└──────────────────────────────────────────────────────────────┘
                        ↓
         ┌──────────────┴──────────────┐
         │                             │
    needs_clarification?               │
         │                             │
    ┌────┴─────┐                       │
    │   TRUE   │                       │   FALSE
    └────┬─────┘                       │
         │                             │
         ↓                             ↓
┌────────────────────┐    ┌─────────────────────────┐
│ Return             │    │ Continue to Stage 2     │
│ Clarification      │    │ (Retrieval)             │
│ Response           │    │                         │
│                    │    │ Use analysis results    │
│ - Specific Qs      │    │ for smart routing       │
│ - Topics           │    │                         │
│ - Cost: $0.001     │    │ Cost: +$0.008           │
│ - Time: 1.0s       │    │ Time: +7.5s             │
└────────────────────┘    └─────────────────────────┘
         │
         ↓
    User provides
    clarification
         │
         ↓
    Back to Stage 1
    (now with context)
```

---

## Implementation

### Enhanced QueryAnalysis Model

```python
from pydantic import BaseModel
from typing import List, Optional

class QueryAnalysis(BaseModel):
    """
    Enhanced query analysis with smart clarification detection.
    """
    # Clarification fields (NEW)
    needs_clarification: bool
    clarification_reason: Optional[str] = None
    clarification_questions: Optional[List[str]] = None
    suggested_topics: Optional[List[str]] = None
    
    # Existing extraction fields
    legal_concepts: List[str]
    articles: List[str]
    keywords: List[str]
    query_type: str  # definition | procedure | rights | calculation
    breadth: str  # specific | moderate | broad
```

### GPT-4o-mini Prompt

```python
CLARIFICATION_ANALYSIS_PROMPT = """
You are analyzing a Philippine labor law query to determine if clarification is needed.

**User's Query**: "{query}"

**Conversation History**:
{format_conversation_history(conversation_history)}

**Task 1: Clarification Detection**

A query NEEDS CLARIFICATION if:
1. Missing critical context
   Example: "What about my case?" → What case? What aspect?
   
2. Ambiguous pronouns without clear referents
   Example: "Can they do this to me?" → Who is "they"? What is "this"?
   
3. Too broad without specific topic
   Example: "Tell me my rights" → Which rights? Termination? Overtime? Leave?
   
4. Unclear intent or incomplete thought
   Example: "I have a problem at work" → What problem specifically?

A query does NOT need clarification if:
1. Specific and self-contained
   Example: "What is 13th month pay eligibility?"
   
2. Context is clear from conversation history
   Example: After discussing 13th month pay, "How is it calculated?"
   (The pronoun "it" clearly refers to 13th month pay)
   
3. It's a valid follow-up question
   Example: "What are the exemptions?" (after discussing a law)

**Task 2: Generate Clarification (if needed)**

If clarification IS needed, provide:
1. **clarification_reason**: Brief explanation of why it's vague (1 sentence)

2. **clarification_questions**: 3-4 SPECIFIC follow-up questions that help narrow down the topic
   BAD: "What do you mean?"
   GOOD: "Are you asking about termination rights, overtime pay, or leave entitlements?"

3. **suggested_topics**: 3-5 common labor law areas the user might be asking about
   Examples: ["Termination", "Overtime Pay", "13th Month Pay", "Maternity Leave"]

**Task 3: Extract Legal Information (ALWAYS do this)**

Even if query is vague, extract what you can:
- Legal concepts mentioned (even if unclear context)
- Any article/law references (e.g., "Article 87", "PD 851")
- Keywords for potential search
- Query type and breadth classification

**Response Format (JSON)**:
{{
  "needs_clarification": true or false,
  "clarification_reason": "string or null",
  "clarification_questions": ["Q1", "Q2", "Q3", "Q4"] or null,
  "suggested_topics": ["Topic1", "Topic2", "Topic3"] or null,
  "legal_concepts": ["concept1", "concept2"],
  "articles": ["Article X", "PD Y"] or [],
  "keywords": ["keyword1", "keyword2"],
  "query_type": "definition|procedure|rights|calculation|comparison",
  "breadth": "specific|moderate|broad"
}}

**Examples**:

Example 1 - NEEDS CLARIFICATION:
Query: "What about my rights?"
Response:
{{
  "needs_clarification": true,
  "clarification_reason": "Query is too broad - unclear which specific employee rights area",
  "clarification_questions": [
    "Are you asking about termination and separation pay rights?",
    "Do you want to know about overtime pay and working hours?",
    "Is this regarding leave entitlements (sick, maternity, vacation)?",
    "Or are you asking about workplace safety and health rights?"
  ],
  "suggested_topics": ["Termination Rights", "Overtime Pay", "Leave Benefits", "Workplace Safety"],
  "legal_concepts": ["employee rights"],
  "articles": [],
  "keywords": ["rights", "employee"],
  "query_type": "rights",
  "breadth": "broad"
}}

Example 2 - DOES NOT NEED CLARIFICATION:
Query: "What is the eligibility for 13th month pay?"
Response:
{{
  "needs_clarification": false,
  "clarification_reason": null,
  "clarification_questions": null,
  "suggested_topics": null,
  "legal_concepts": ["13th month pay", "eligibility"],
  "articles": ["PD 851"],
  "keywords": ["13th month pay", "eligibility", "qualification"],
  "query_type": "definition",
  "breadth": "specific"
}}

Example 3 - CONTEXT-AWARE (Multi-turn):
Conversation:
User: "What is 13th month pay?"
Assistant: [Explained PD 851...]

Current Query: "How is it calculated?"

Response:
{{
  "needs_clarification": false,  // "it" clearly = "13th month pay" from context
  "clarification_reason": null,
  "clarification_questions": null,
  "suggested_topics": null,
  "legal_concepts": ["13th month pay calculation"],
  "articles": ["PD 851"],
  "keywords": ["calculation", "computation", "13th month pay"],
  "query_type": "procedure",
  "breadth": "specific"
}}
"""
```

### Updated Chat Orchestrator

```python
async def process_message(
    self,
    session_id: str,
    conversation_id: str,
    user_message: str,
    language: str = "en",
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    
    start_time = time.time()
    
    # Step 1: Add user message to history
    await self.conversation.add_user_message(
        session_id=conversation_id,
        content=user_message
    )
    
    # Step 2: Get conversation history for context-aware analysis
    conversation_history = await self.conversation.get_conversation_context(
        session_id=conversation_id,
        include_last_n=5  # Last 5 messages for pronoun resolution
    )
    
    # Step 3: Analyze query with GPT-4o-mini (includes clarification check)
    logger.info("Analyzing query for clarity and legal concepts")
    
    query_analysis = await self.query_analyzer.analyze(
        query=user_message,
        conversation_history=conversation_history,
        language=language
    )
    
    # Step 4: Check if clarification is needed (SMART CHECK)
    if query_analysis.needs_clarification:
        logger.info(
            f"Query needs clarification: {query_analysis.clarification_reason}"
        )
        
        # Build and return clarification response (STOP PIPELINE)
        clarification_response = self._build_clarification_response(
            analysis=query_analysis,
            language=language
        )
        
        # Add clarification to conversation history
        await self.conversation.add_assistant_message(
            session_id=conversation_id,
            content=clarification_response["content"]
        )
        
        processing_time = time.time() - start_time
        
        return {
            "message_id": str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": clarification_response["content"],
            "timestamp": datetime.utcnow(),
            "citations": [],  # No citations for clarification
            "suggestions": clarification_response["suggestions"],
            "metadata": {
                "processing_time": round(processing_time, 2),
                "is_clarification": True,
                "clarification_reason": query_analysis.clarification_reason,
                "model": "gpt-4o-mini",
                "tokens_used": 500  # Approximate
            }
        }
    
    # Step 5: Proceed with full pipeline (query is clear)
    logger.info("Query is clear, proceeding with retrieval")
    
    # Use analysis results for smart retrieval routing
    if query_analysis.articles:
        # Direct article lookup (fast path - 0.2s)
        retrieval_results = await self.retrieval.direct_lookup(
            articles=query_analysis.articles
        )
    else:
        # Multi-strategy retrieval
        retrieval_results = await self.retrieval.smart_retrieve(
            query=user_message,
            analysis=query_analysis
        )
    
    # ... continue with grounding, generation, etc.


def _build_clarification_response(
    self,
    analysis: QueryAnalysis,
    language: str
) -> Dict[str, Any]:
    """
    Build clarification response with specific follow-up questions.
    """
    if language == "fil":
        intro = "Masaya akong tumulong! Maaari mo bang linawin ang iyong tanong?"
        topics_intro = "Mga posibleng paksa:"
    elif language == "ceb":
        intro = "Malipay ko nga motabang! Mahimo ba nimo nga klaruhon ang imong pangutana?"
        topics_intro = "Mga posibleng topiko:"
    else:
        intro = "I'd be happy to help clarify! Could you provide more details?"
        topics_intro = "Common topics you might be asking about:"
    
    # Build response text
    content_parts = [intro, ""]
    
    # Add specific clarification questions
    if analysis.clarification_questions:
        content_parts.extend(analysis.clarification_questions)
        content_parts.append("")
    
    # Add suggested topics
    if analysis.suggested_topics:
        content_parts.append(topics_intro)
        for topic in analysis.suggested_topics:
            content_parts.append(f"• {topic}")
    
    content = "\n".join(content_parts)
    
    # Build suggested actions (clickable topic buttons)
    suggestions = []
    if analysis.suggested_topics:
        for topic in analysis.suggested_topics[:4]:  # Limit to 4
            suggestions.append({
                "type": "topic",
                "label": topic,
                "action": f"Tell me about {topic.lower()}"
            })
    
    return {
        "content": content,
        "suggestions": suggestions
    }
```

---

## Performance Impact

### Vague Query Savings (30% of queries)

**Before (Full Pipeline)**:
- Retrieval: 2.0s
- LLM Grounding: 4.5s
- Total: 7.5s
- Cost: $0.008

**After (Clarification Only)**:
- Query Analysis: 1.0s
- Total: 1.0s (87% faster)
- Cost: $0.001 (87% cheaper)

### Clear Query Overhead (70% of queries)

**Before**:
- Retrieval: 2.0s
- LLM Grounding: 4.5s
- Total: 7.5s
- Cost: $0.008

**After**:
- Query Analysis: 1.0s (NEW)
- Retrieval: 2.0s
- LLM Grounding: 4.5s
- Total: 8.5s (13% slower)
- Cost: $0.009 (12% more expensive)

### Net Impact (assuming 30% vague, 70% clear)

**Monthly (10,000 queries)**:
- Current: 10,000 × $0.008 = $80
- With Smart Clarification:
  - 3,000 vague × $0.001 = $3
  - 7,000 clear × $0.009 = $63
  - Total: $66 (18% cheaper)

**Average Latency**:
- Current: 7.5s
- With Smart Clarification: (0.3 × 1.0s) + (0.7 × 8.5s) = 6.25s (17% faster)

**User Experience**:
- Fewer irrelevant answers (vague queries get proper guidance)
- Better first-time user experience (helps frame questions)
- Reduced frustration from generic responses

---

## Test Cases

### Test 1: Vague Query Detection

```python
async def test_vague_query_clarification():
    query = "What about my rights?"
    
    response = await chat_orchestrator.process_message(
        session_id="test_session",
        conversation_id="conv_123",
        user_message=query,
        language="en"
    )
    
    assert response["metadata"]["is_clarification"] == True
    assert len(response["suggestions"]) >= 3
    assert "termination" in response["content"].lower()  # Common topic
    assert response["metadata"]["processing_time"] < 1.5
```

### Test 2: Clear Query Bypasses Clarification

```python
async def test_clear_query_no_clarification():
    query = "What is the eligibility for 13th month pay?"
    
    response = await chat_orchestrator.process_message(
        session_id="test_session",
        conversation_id="conv_123",
        user_message=query,
        language="en"
    )
    
    assert response["metadata"].get("is_clarification", False) == False
    assert len(response["citations"]) > 0  # Full pipeline executed
    assert "PD 851" in str(response["citations"])
```

### Test 3: Context-Aware Follow-up

```python
async def test_context_aware_followup():
    # Turn 1: Clear query
    response1 = await chat_orchestrator.process_message(
        session_id="test_session",
        conversation_id="conv_123",
        user_message="What is 13th month pay?",
        language="en"
    )
    assert response1["metadata"].get("is_clarification", False) == False
    
    # Turn 2: Follow-up with pronoun (should NOT trigger clarification)
    response2 = await chat_orchestrator.process_message(
        session_id="test_session",
        conversation_id="conv_123",
        user_message="How is it calculated?",  # "it" = 13th month pay
        language="en"
    )
    
    assert response2["metadata"].get("is_clarification", False) == False
    assert "calculation" in response2["content"].lower()
```

### Test 4: Multilingual Clarification

```python
async def test_filipino_clarification():
    query = "Ano yung karapatan ko?"  # "What about my rights?"
    
    response = await chat_orchestrator.process_message(
        session_id="test_session",
        conversation_id="conv_123",
        user_message=query,
        language="fil"
    )
    
    assert response["metadata"]["is_clarification"] == True
    assert "termination" in response["content"].lower() or "terminasyon" in response["content"].lower()
    assert len(response["suggestions"]) >= 3
```

---

## Monitoring & Metrics

### Key Performance Indicators

```python
# Track in performance dashboard
metrics = {
    "clarification_rate": {
        "description": "% of queries triggering clarification",
        "target": "20-30%",
        "alert_threshold": ">40% (too aggressive) or <10% (too lenient)"
    },
    "clarification_latency": {
        "description": "Time to return clarification response",
        "target": "<1.5s",
        "alert_threshold": ">2.0s"
    },
    "clarification_quality": {
        "description": "% of clarifications with 3+ specific questions",
        "target": ">90%",
        "alert_threshold": "<80%"
    },
    "follow_up_rate": {
        "description": "% of clarifications followed by specific query",
        "target": ">60%",
        "alert_threshold": "<40% (users giving up)"
    },
    "false_clarification_rate": {
        "description": "% of clear queries falsely flagged",
        "target": "<5%",
        "measurement": "Manual review of sample"
    }
}
```

### Logging

```python
# Add structured logging
logger.info(
    "Clarification triggered",
    extra={
        "query": user_message,
        "reason": analysis.clarification_reason,
        "num_questions": len(analysis.clarification_questions),
        "suggested_topics": analysis.suggested_topics,
        "latency": processing_time,
        "conversation_turns": len(conversation_history)
    }
)
```

---

## Rollback Plan

**IF** smart clarification has issues:

1. **Add feature flag** to `core/config.py`:
   ```python
   ENABLE_SMART_CLARIFICATION: bool = True
   ```

2. **Fallback to deterministic**:
   ```python
   if settings.ENABLE_SMART_CLARIFICATION:
       if query_analysis.needs_clarification:
           return clarification_response
   else:
       # Old deterministic approach
       if self.conversation.is_clarification_needed(user_message):
           return self._generate_fallback_clarification(user_message)
   ```

3. **Rollback trigger criteria**:
   - Clarification rate >50% (too aggressive)
   - False clarification rate >15% (manual review)
   - User complaints/feedback indicating frustration
   - Performance degradation (>2s clarification latency)

---

## Future Enhancements

### Phase 2.x: Clarification Learning
- Track which clarification questions lead to successful queries
- Optimize question generation based on user selections
- Personalize clarifications based on user history

### Phase 3.x: Proactive Clarification
- Detect ambiguity in mid-complexity queries
- Offer optional clarifications without blocking pipeline
- "I assume you mean X, but if you meant Y..."

---

## References

- [ADR-002: RAG Pipeline Architecture](./adr/002-rag-pipeline-limitations-and-future-architecture.md)
- [Phase 1.0.5 Architecture Revision](./PHASE_1.0.5_ARCHITECTURE_REVISION.md)
- [Implementation Sequence](../ImplementationSequence.md)
- [Implementation Checklist](./PHASE_1.0.5_IMPLEMENTATION_CHECKLIST.md)

---

**Approved**: November 11, 2025  
**Next Steps**: Implement in Day 1 of Phase 1.0.5
