# Step 5: Frontend Connection Testing Guide

**Date**: November 23, 2025  
**Status**: Manual Testing in Progress  
**Critical Issues Identified**: Streaming response not working, citation formatting issues

---

## Prerequisites Checklist

- [ ] Backend running on `http://localhost:8000`
- [ ] Frontend running on `http://localhost:3000`
- [ ] Database connection verified
- [ ] Test user account created (if auth enabled)

**Quick Start Backend**:
```powershell
# Activate venv
.\.venv\Scripts\Activate.ps1

# Run server
uvicorn app.main:app --reload --port 8000
```

---

## Test Scenarios

### A. Basic Chat Flow (Priority: HIGH)

**Query**: "What is overtime pay?"

**Expected Behavior**:
- ✅ Response streams token-by-token
- ✅ 3-5 citations appear at end
- ✅ Total response time <9s
- ✅ Citations link to correct articles (PD 851, RA 10361, Labor Code)

**Actual Behavior**:
- [ ] Streaming: ___________
- [ ] Citations count: ___________
- [ ] Response time: ___________
- [ ] Citation format: ___________

**Issues Found**:
```
[Document issues here]
```

---

### B. Clarification Flow (Priority: HIGH)

**Query**: "Tell me about leave"

**Expected Behavior**:
- ✅ System detects vague query
- ✅ Clarification message appears
- ✅ 3-4 specific follow-up questions shown
- ✅ Response time <1.5s

**Follow-up**: Click "Maternity leave" or send as new query

**Actual Behavior**:
- [ ] Clarification triggered: ___________
- [ ] Follow-up questions shown: ___________
- [ ] Response time: ___________

**Issues Found**:
```
[Document issues here]
```

---

### C. Multi-turn Conversation (Priority: MEDIUM)

**Turn 1**: "What is the minimum wage?"
- Expected: Answer with citations
- Actual: ✅ Working

**Turn 2**: "How often is it updated?"
- Expected: Context-aware (no clarification needed)
- Actual: ❌ **FIXED** - Was requesting clarification (multi-turn broken)

**Turn 3**: "What if I'm in Cebu?"
- Expected: Location-specific answer
- Actual: ⏳ Pending retest

**Issues Found & Fixed**:
```
Issue: Multi-turn conversation broken in process_message_stream
Root Cause: Conversation history was retrieved AFTER adding current message,
            causing the current query to appear in the context, confusing the
            query analysis LLM.
Fix: Reordered steps to get conversation history BEFORE adding current message.
     This ensures query analysis only sees PREVIOUS messages for context.
File: services/chat_orchestrator.py (both process_message and process_message_stream)
Status: FIXED - Ready for retest
```

---

### D. Streaming UX (Priority: HIGH)

**Query**: "How to calculate 13th month pay?"

**Check Points**:
- [ ] First token appears within 3.5s
- [ ] Tokens stream smoothly (no long pauses)
- [ ] No UI flicker or layout shifts
- [ ] Citations appear after main text completes
- [ ] Loading indicator shows during streaming

**Actual Behavior**:
- First token time: ___________
- Streaming quality: ___________
- UI stability: ___________

**Issues Found**:
```
[Document issues here]
```

---

### E. Error Handling (Priority: MEDIUM)

**Test 1 - Gibberish Input**:
- Query: "asdfghjkl"
- Expected: Polite error or "I can only answer labor law questions"
- Actual: ___________

**Test 2 - Disconnect During Streaming**:
- Action: Stop/cancel request mid-stream
- Expected: Backend handles gracefully, no crash
- Actual: ___________

---

## Known Issues to Verify

### Issue 1: Streaming Not Working
**Symptoms**: Full response appears at once instead of token-by-token

**Check**:
1. Browser Network tab shows `text/event-stream` content type?
2. Frontend uses `EventSource` or `fetch` with streaming reader?
3. Backend `/v1/chat` endpoint returns SSE format?

**Debug Commands**:
```powershell
# Test SSE endpoint directly
curl -N -H "Content-Type: application/json" -d '{\"message\":\"What is overtime pay?\",\"conversation_id\":\"test-123\"}' http://localhost:8000/api/v1/chat/message/stream
```

**Expected Output**:
```
event: status
data: {"step":"analyze","message":"Analyzing your query..."}

event: status
data: {"step":"retrieve","message":"Searching labor laws..."}

event: metadata
data: {"retrieval_time":1.2,"citations_count":5}

event: status
data: {"step":"generate","message":"Formulating response..."}

event: content_chunk
data: {"text":"Overtime"}

event: content_chunk
data: {"text":" pay"}

...

event: citations
data: [{"article_id":"PD-851-Art-1","title":"..."}]

event: complete
data: {"message_id":"..."}
```

---

### Issue 2: Citation Formatting Issues
**Symptoms**: Citations missing, malformed, or not clickable

**Check**:
1. Citation format in response matches frontend expectations?
2. Article numbers and titles present?
3. Citation links/IDs valid?

**Expected Citation Format**:
```json
{
  "article_id": "PD-851-Art-1",
  "title": "PD 851: 13th Month Pay Law",
  "excerpt": "All employers are required to pay...",
  "source": "Presidential Decree No. 851"
}
```

**Actual Format**:
```
[Paste actual citation JSON here]
```

---

## Evaluation Criteria

| Test | Pass/Fail | Notes |
|------|-----------|-------|
| A. Basic Chat Flow | ⏳ | |
| B. Clarification Flow | ⏳ | |
| C. Multi-turn Conversation | ⏳ | |
| D. Streaming UX | ⏳ | |
| E. Error Handling | ⏳ | |

**Overall Status**: ⏳ Testing in Progress

---

## Issue Triage Template

For each issue found, document:

**Issue #**: [Number]  
**Severity**: Critical / High / Medium / Low  
**Component**: Frontend / Backend / Both  
**Symptoms**: [What you observe]  
**Expected**: [What should happen]  
**Steps to Reproduce**: [Minimal steps]  
**Logs/Screenshots**: [Attach if available]  

---

## Next Steps After Testing

1. Document all issues found
2. Prioritize by severity (Critical → Low)
3. For each critical issue:
   - Identify root cause (frontend vs backend)
   - Propose fix
   - Implement and retest
4. Update checklist with final results

---

**Testing By**: [Your Name]  
**Date Completed**: November 23, 2025  
**Total Issues Found**: 1 (Critical - Multi-turn conversation broken)  
**Critical Issues**: 1 (FIXED)

---

## Critical Fix Applied - Multi-turn Conversation

**Problem**: When asking follow-up questions like "How often is it updated?" after "What is the minimum wage?", the system was requesting clarification instead of understanding the context.

**Root Cause**: 
In `process_message_stream()`, the conversation history was retrieved AFTER adding the current user message. This meant:
- Current query: "How often is it updated?"
- Conversation history passed to query analysis:
  ```
  USER: What is the minimum wage?
  ASSISTANT: [response]
  USER: How often is it updated?  ← CURRENT MESSAGE INCLUDED!
  ```
- The LLM saw the current query TWICE (once in history, once as the query to analyze), making it unable to resolve pronoun "it"

**Solution**:
Reordered steps in both `process_message()` and `process_message_stream()`:
1. **Get conversation history FIRST** (only previous messages)
2. **Then add current user message** (after analysis)

Now the query analysis sees proper context:
```
Previous conversation:
USER: What is the minimum wage?
ASSISTANT: [response about minimum wage]

Current query: "How often is it updated?"
```

The LLM can now resolve "it" → "minimum wage" → no clarification needed.

**Files Modified**: `services/chat_orchestrator.py` (Lines 96-111 and 571-581)

**Status**: ✅ **FIXED** - Ready for retest

### Investigation: single-turn clarification behavior

Summary: During investigation we observed that some clear, single-turn legal queries
(for example, "What is the minimum wage?") were being classified by the query analysis
LLM as "needs_clarification". This can be a valid behavior for genuinely ambiguous
questions, but in practice it produced too many false positives for short, topic-specific
legal questions.

Action taken (non-invasive): Added a small post-LLM heuristic in the query analysis
pipeline that clears the `needs_clarification` flag when strong topic signals are
present (e.g., presence of keywords like "minimum wage", extracted article references,
or detected legal concepts). This change does NOT modify the `_build_analysis_prompt`
and therefore keeps the original LLM instructions intact while reducing unnecessary
clarification prompts for clearly-scoped legal questions.

Effect: After this change, single-turn queries such as "What is the minimum wage?"
should receive a direct answer rather than a clarification request, while vague
questions (e.g., "What are my rights?") still trigger clarification as intended.

Files changed:
- `services/pipeline/query_analysis.py` — added post-LLM clarification override heuristic

Status: ✅ Implemented — ready for retest (please re-run Basic Chat Flow A and Multi-turn
tests to confirm behavior)
