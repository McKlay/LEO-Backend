# Multi-Turn Context Investigation Plan

**Issue**: Follow-up queries in conversations not maintaining context  
**Impact**: 4/6 multi-turn tests failing (33% accuracy)  
**Severity**: CRITICAL - Core feature broken

---

## Problem Description

### Expected Behavior
```
Turn 1: "What is overtime pay?"
  → Bot answers with overtime pay details

Turn 2: "How is it calculated?"  
  → Bot answers: "Overtime pay is calculated at 150% of hourly rate..."
```

### Actual Behavior
```
Turn 1: "What is overtime pay?"
  → ✅ Bot answers correctly

Turn 2: "How is it calculated?"
  → ❌ Bot asks: "I need clarification. How is what calculated?"
```

### Test Script Status
✅ Fixed to use shared `conversation_id` across turns  
❌ Backend still not using conversation history

---

## Investigation Steps

### Step 1: Verify Memory Adapter (15 min)

**Check**: Is LangChainMemory persisting messages?

```python
# Test script: scripts/test_memory_persistence.py
import asyncio
from app.containers import get_memory_adapter

async def test():
    memory = get_memory_adapter()
    conv_id = "test_conv_123"
    
    # Add messages
    await memory.append(conv_id, "user", "What is overtime pay?")
    await memory.append(conv_id, "assistant", "Overtime pay is...")
    
    # Retrieve
    history = await memory.get_messages(conv_id)
    print(f"History length: {len(history)}")
    print(f"Messages: {history}")
    
    # Test retrieval again
    history2 = await memory.get_messages(conv_id)
    print(f"Second retrieval: {len(history2)} messages")

asyncio.run(test())
```

**Expected**: Should see 2 messages on both retrievals

### Step 2: Check ConversationPipeline (20 min)

**Check**: Is `get_conversation_context()` retrieving history?

```python
# Add logging to services/pipeline/conversation.py

async def get_conversation_context(
    self,
    conversation_id: str,
    max_turns: int = 3
) -> str:
    history = await self.memory.get_messages(conversation_id)
    
    # ADD THIS DEBUG LOGGING
    self.logger.info(
        f"Retrieved conversation history for {conversation_id}: "
        f"{len(history)} messages"
    )
    if history:
        self.logger.info(f"Last message: {history[-1]}")
    
    # ... rest of method
```

**Run test**, check logs for:
- Conversation ID matches
- History is non-empty
- Last message is from previous turn

### Step 3: Check QueryAnalysisPipeline (20 min)

**Check**: Is conversation context being used in analysis?

```python
# Add logging to services/pipeline/query_analysis.py

async def analyze(
    self,
    query: str,
    conversation_context: Optional[str] = None
) -> QueryAnalysis:
    # ADD THIS DEBUG LOGGING
    self.logger.info(
        f"Query analysis - Input query: '{query}', "
        f"Has context: {bool(conversation_context)}, "
        f"Context length: {len(conversation_context or '')}"
    )
    
    # ... rest of method
```

**Expected**: When Turn 2 runs, should see:
- `Has context: True`
- `Context length: >100` (previous exchange)

### Step 4: Check LLM Prompt (15 min)

**Check**: Is conversation history in the prompt sent to GPT-4o-mini?

```python
# In query_analysis.py, log the actual prompt

messages = [...]  # constructed messages

# ADD THIS BEFORE CALLING LLM
self.logger.debug(f"Prompt to LLM: {json.dumps(messages, indent=2)}")

result = await self.llm.generate(messages, stream=False)
```

**Expected**: System message should include conversation context:
```json
{
  "role": "system",
  "content": "...Previous conversation:\nUser: What is overtime pay?\nAssistant: Overtime pay is...\n\nCurrent query: How is it calculated?"
}
```

### Step 5: Manual API Test (10 min)

**Test with curl** to isolate from test script:

```powershell
# Turn 1
$response1 = Invoke-RestMethod -Method POST `
  -Uri "http://localhost:8000/v1/chat" `
  -ContentType "application/json" `
  -Body (@{
    message = "What is overtime pay?"
    session_id = "manual_test_123"
    conversation_id = "conv_manual_123"
  } | ConvertTo-Json)

Write-Host "Turn 1 Response: $($response1.response | Select -First 200)"

# Turn 2 - Same conversation_id
$response2 = Invoke-RestMethod -Method POST `
  -Uri "http://localhost:8000/v1/chat" `
  -ContentType "application/json" `
  -Body (@{
    message = "How is it calculated?"
    session_id = "manual_test_123"
    conversation_id = "conv_manual_123"
  } | ConvertTo-Json)

Write-Host "Turn 2 Response: $($response2.response | Select -First 200)"
```

**Expected**: Turn 2 should answer about overtime calculation, not ask "what?"

---

## Likely Root Causes (Priority Order)

### 1. Memory Not Persisting Between Calls (60% probability)
**Symptom**: `get_messages()` returns empty list  
**Cause**: 
- Memory instance not shared (new instance per request)
- LangChain memory needs explicit save call
- Conversation ID mismatch

**Fix**: Ensure memory is singleton, check save logic

### 2. Conversation Context Not Passed to Analysis (25% probability)
**Symptom**: `conversation_context=None` in query analysis  
**Cause**: `ChatOrchestrator` not calling `get_conversation_context()` before analysis

**Fix**: Check orchestrator flow, ensure context passed to `analyze()`

### 3. LLM Ignoring Context in Prompt (10% probability)
**Symptom**: Context in prompt but LLM still asks for clarification  
**Cause**: 
- Prompt format unclear
- Context buried in long system message
- LLM preferring safe clarification

**Fix**: Adjust prompt to emphasize context usage

### 4. Smart Clarification Too Aggressive (5% probability)
**Symptom**: Query classified as vague even with context  
**Cause**: Confidence threshold too low, pronoun resolution not working

**Fix**: Adjust clarification criteria when context exists

---

## Quick Diagnostic

**Run this one-liner to check if it's a memory issue**:

```python
# In chat_orchestrator.py, after processing message:
print(f"DEBUG: Saved to memory? conv_id={conversation_id}, "
      f"history_len={len(await self.conversation.memory.get_messages(conversation_id))}")
```

**If history_len=0 after Turn 1**: Memory not persisting → Fix memory adapter  
**If history_len=2 after Turn 1**: Memory working → Check context passing  

---

## Success Criteria

After fixes, this should work:

```python
# Manual test
Turn 1: "What is maternity leave?"
  → Answer with maternity leave details

Turn 2: "How long is it?"
  → Answer: "Maternity leave in the Philippines is 105 days..."
  → NOT: "How long is what?"

Turn 3: "Do I get paid?"
  → Answer: "Yes, maternity leave is paid at 100% of salary..."
  → NOT: "Do you get paid for what?"
```

**Target**: 5/6 multi-turn tests passing (83%)  
**Current**: 2/6 passing (33%)  
**Improvement needed**: +3 tests = +50 percentage points

---

## Time Estimate

- Investigation: 1-2 hours
- Fix implementation: 30 min - 2 hours (depending on root cause)
- Re-testing: 15 min
- **Total**: 2-4 hours

---

## Next Steps

1. Run Step 1 (test_memory_persistence.py)
2. Based on results, add logging to appropriate module
3. Run multi-turn test with logging enabled
4. Analyze logs to identify exact failure point
5. Implement fix
6. Re-run accuracy tests
7. Document resolution

**Start with**: Memory persistence test (highest probability root cause)
