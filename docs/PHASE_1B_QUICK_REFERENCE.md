# Phase 1.B Quick Reference Guide

## Usage Examples

### 1. Using Embeddings Adapter

```python
from app.containers import get_embeddings_adapter

# Get singleton instance
embeddings = get_embeddings_adapter()

# Single text embedding
response = await embeddings.embed_text("What are overtime pay rules?")
print(f"Embedding: {len(response.embedding)} dimensions")
print(f"Tokens used: {response.tokens_used}")

# Batch embedding
texts = ["query 1", "query 2", "query 3"]
responses = await embeddings.embed_batch(texts, batch_size=2)
for r in responses:
    print(f"Vector: {len(r.embedding)}D, Tokens: {r.tokens_used}")
```

---

### 2. Using LLM Adapter

```python
from app.containers import get_llm_adapter

# Get singleton instance
llm = get_llm_adapter()

# Standard generation
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Explain overtime pay in the Philippines."}
]

response = await llm.generate(messages, temperature=0.3, max_tokens=500)
print(f"Response: {response.content}")
print(f"Tokens: {response.usage['total_tokens']}")

# Streaming generation
async for chunk in llm.stream(messages, temperature=0.3, max_tokens=500):
    print(chunk, end="", flush=True)
```

---

### 3. Using Vector Store Adapter

```python
from app.containers import get_vectorstore_adapter, get_embeddings_adapter
from adapters.vectorstore.base import Document

# Get instances
vectorstore = get_vectorstore_adapter()
embeddings = get_embeddings_adapter()

# Upsert documents
documents = [
    Document(
        id="doc_1",
        content="Article 87 of the Labor Code covers overtime pay...",
        metadata={"source": "Labor Code", "article": "87"}
    )
]

count = await vectorstore.upsert(documents)
print(f"Upserted {count} documents")

# Query
query_text = "What are the overtime pay rules?"
query_embedding = await embeddings.embed_text(query_text)

results = await vectorstore.query(
    query_vector=query_embedding.embedding,
    top_k=5,
    filters={"source": "Labor Code"}
)

for r in results:
    print(f"[{r.similarity_score:.2f}] {r.content[:100]}...")
```

---

### 4. Using Memory Adapter

```python
from app.containers import get_memory_adapter

# Get singleton instance
memory = get_memory_adapter()

session_id = "user_session_123"

# Add messages
await memory.add_message(session_id, "user", "Hello, I need help.")
await memory.add_message(session_id, "assistant", "Hi! How can I assist you?")
await memory.add_message(session_id, "user", "Tell me about overtime pay.")

# Get history
history = await memory.get_history(session_id, limit=5)
for msg in history.messages:
    print(f"{msg.role}: {msg.content}")

# Clear history
await memory.clear_history(session_id)
```

---

### 5. Using Retrieval Pipeline

```python
from app.containers import get_retrieval_pipeline

# Get singleton instance
retrieval = get_retrieval_pipeline()

# Retrieve relevant context
results = await retrieval.retrieve(
    query="What are maternity leave benefits?",
    top_k=3,
    intent_category="employee_benefits"
)

print(f"Found {len(results)} relevant documents")

# Format as context string
context = retrieval.format_context(results)
print(context)

# Extract citations
citations = retrieval.extract_citations(results)
for c in citations:
    print(f"[{c['id']}] {c['source']} (similarity: {c['similarity']})")
```

---

### 6. Using Grounding Pipeline

```python
from app.containers import get_grounding_pipeline, get_retrieval_pipeline

# Get instances
grounding = get_grounding_pipeline()
retrieval = get_retrieval_pipeline()

# Retrieve context
query = "What are the rules for overtime pay?"
results = await retrieval.retrieve(query, top_k=3)

# Build grounded prompt
messages = grounding.build_grounded_prompt(
    query=query,
    context_results=results,
    language="en",
    conversation_history=[
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi! How can I help?"}
    ]
)

print(f"Built {len(messages)} messages for LLM")
print(f"System prompt length: {len(messages[0]['content'])} chars")

# Extract citation metadata
citations = grounding.extract_citation_metadata(results)
print(f"Citations: {citations}")
```

---

### 7. Using Generation Pipeline

```python
from app.containers import get_generation_pipeline, get_grounding_pipeline

# Get instances
generation = get_generation_pipeline()

# Prepare messages (from grounding pipeline)
messages = [
    {"role": "system", "content": "You are a labor law expert..."},
    {"role": "user", "content": "Explain overtime pay rules."}
]

# Standard generation
response = await generation.generate(
    messages=messages,
    temperature=0.3,
    max_tokens=500
)
print(f"Response: {response.content}")

# Streaming generation
print("Streaming response:")
async for chunk in generation.generate_stream(messages):
    print(chunk, end="", flush=True)

# Generation with retry
response = await generation.generate_with_retry(
    messages=messages,
    max_retries=2
)
```

---

### 8. Using Postprocess Pipeline

```python
from app.containers import get_postprocess_pipeline

# Get singleton instance
postprocess = get_postprocess_pipeline()

# Mock LLM response with citations
llm_response = """
Overtime pay is mandatory in the Philippines [1]. 
Employees must receive at least 125% of their regular rate [2].
"""

citations = [
    {
        "id": 1,
        "source": "Labor Code Article 87",
        "url": "https://example.com/labor-code/87"
    },
    {
        "id": 2,
        "source": "DOLE Guidelines",
        "url": None
    }
]

# Process response
result = postprocess.process_response(
    response=llm_response,
    citations=citations,
    language="en",
    add_disclaimer=True
)

print("Processed response:")
print(result["content"])
print(f"\nHas disclaimer: {result['has_disclaimer']}")
print(f"Citation count: {result['citation_count']}")

# Generate suggested actions
suggestions = postprocess.generate_suggested_actions(
    response=llm_response,
    citations=citations,
    language="en"
)
print(f"\nSuggested actions: {suggestions}")
```

---

### 9. Using Conversation Pipeline

```python
from app.containers import get_conversation_pipeline

# Get singleton instance
conversation = get_conversation_pipeline()

session_id = "user_123"

# Add messages to conversation
await conversation.add_user_message(session_id, "Hello")
await conversation.add_assistant_message(session_id, "Hi! How can I help?")
await conversation.add_user_message(session_id, "Tell me about overtime pay")

# Get conversation context for LLM
context = await conversation.get_conversation_context(
    session_id=session_id,
    include_last_n=5
)
print(f"Context messages: {len(context)}")

# Get conversation summary
summary = await conversation.get_conversation_summary(session_id)
print(f"Total messages: {summary['total_messages']}")
print(f"User messages: {summary['user_messages']}")
print(f"Assistant messages: {summary['assistant_messages']}")

# Check if clarification needed
vague_query = "help"
if conversation.is_clarification_needed(vague_query):
    print("Query is too vague, needs clarification")
```

---

### 10. Full RAG Pipeline Example

```python
from app.containers import (
    get_retrieval_pipeline,
    get_grounding_pipeline,
    get_generation_pipeline,
    get_postprocess_pipeline,
    get_conversation_pipeline
)

async def process_user_query(session_id: str, query: str, language: str = "en"):
    """Complete RAG pipeline flow."""
    
    # 1. Get conversation history
    conversation = get_conversation_pipeline()
    history = await conversation.get_conversation_context(session_id)
    
    # 2. Check if clarification needed
    if conversation.is_clarification_needed(query):
        generation = get_generation_pipeline()
        clarification = await generation.generate_clarification(query, language)
        await conversation.add_user_message(session_id, query)
        await conversation.add_assistant_message(session_id, clarification)
        return clarification
    
    # 3. Retrieve relevant context
    retrieval = get_retrieval_pipeline()
    results = await retrieval.retrieve(query, top_k=5)
    
    if not results:
        return "I don't have enough information to answer that question."
    
    # 4. Build grounded prompt
    grounding = get_grounding_pipeline()
    messages = grounding.build_grounded_prompt(
        query=query,
        context_results=results,
        language=language,
        conversation_history=history
    )
    citations = grounding.extract_citation_metadata(results)
    
    # 5. Generate response
    generation = get_generation_pipeline()
    response = await generation.generate_with_retry(messages, max_retries=2)
    
    # 6. Postprocess response
    postprocess = get_postprocess_pipeline()
    processed = postprocess.process_response(
        response=response.content,
        citations=citations,
        language=language,
        add_disclaimer=True
    )
    
    # 7. Update conversation history
    await conversation.add_user_message(session_id, query)
    await conversation.add_assistant_message(session_id, processed["content"])
    
    # 8. Generate suggestions
    suggestions = postprocess.generate_suggested_actions(
        response=response.content,
        citations=citations,
        language=language
    )
    
    return {
        "content": processed["content"],
        "citations": citations,
        "suggestions": suggestions,
        "metadata": {
            "tokens_used": response.usage.get("total_tokens", 0),
            "sources_count": len(results)
        }
    }

# Usage
result = await process_user_query(
    session_id="user_123",
    query="What are the overtime pay rules in the Philippines?",
    language="en"
)

print(result["content"])
print(f"\nCitations: {len(result['citations'])}")
print(f"Suggestions: {result['suggestions']}")
```

---

## Configuration Reference

### Environment Variables

```env
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_LLM_MODEL=gpt-4-turbo-preview
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
LLM_TEMPERATURE=0.3
LLM_MAX_TOKENS=1000
ENABLE_STREAMING=true

# Supabase
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJxxx...

# Vector Store
VECTORSTORE_TABLE_NAME=labor_law_embeddings
EMBEDDING_DIMENSION=1536
RETRIEVAL_TOP_K=5
RETRIEVAL_SIMILARITY_THRESHOLD=0.7

# Memory
MEMORY_TOKEN_LIMIT=4000
MAX_HISTORY_MESSAGES=10
CONTEXT_WINDOW_TOKENS=4000

# Processing
MAX_CONTEXT_LENGTH=8000
ENABLE_AUTO_DISCLAIMER=true
ENABLE_PII_REDACTION=false
```

---

## Testing

### Run Integration Tests

```powershell
# All Phase 1.B tests
pytest tests/integration/test_phase1b_infrastructure.py -v

# Specific test class
pytest tests/integration/test_phase1b_infrastructure.py::TestRetrievalPipeline -v

# With coverage
pytest tests/integration/test_phase1b_infrastructure.py --cov=adapters --cov=services/pipeline -v
```

---

## Common Patterns

### Error Handling

```python
from core.exceptions import AppError

try:
    response = await llm.generate(messages)
except AppError as e:
    print(f"Error code: {e.error_code}")
    print(f"Message: {e.message}")
    print(f"Details: {e.details}")
```

### Async Context

All adapter and pipeline methods are async, so use `await`:

```python
# ✅ Correct
result = await embeddings.embed_text("query")

# ❌ Wrong
result = embeddings.embed_text("query")  # Returns coroutine, not result
```

### Singleton Access

All adapters and pipelines are singletons via containers:

```python
# ✅ Correct - reuses same instance
llm1 = get_llm_adapter()
llm2 = get_llm_adapter()
assert llm1 is llm2  # True

# ❌ Wrong - creates new instances
llm1 = OpenAILLM(api_key, model)
llm2 = OpenAILLM(api_key, model)
assert llm1 is llm2  # False
```

---

## Next Steps

With Phase 1.B complete, proceed to **Phase 1.C: Chat API Implementation**:

1. Create `api/v1/routes_chat.py` with POST `/api/v1/chat/message` endpoint
2. Define Pydantic request/response schemas
3. Integrate authentication middleware (from Phase 1.A)
4. Add rate limiting enforcement
5. Implement the full RAG pipeline orchestration
6. Add comprehensive integration tests

All infrastructure is ready! 🚀
