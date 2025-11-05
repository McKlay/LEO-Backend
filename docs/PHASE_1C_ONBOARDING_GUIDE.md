# LEO Backend - Onboarding Guide

**Welcome to the LEO Backend Project!**  
**Date**: January 2025  
**Your Current Phase**: Between Phase 1.C ✅ and Phase 1.D 

---

## Quick Answers to Your Questions

### Q1: When can we test the actual LLM?

**Answer**: **RIGHT NOW!**

You **already have** the LLM integrated and ready to test. Here's what's been implemented:

#### ✅ What's Already Working:

1. **OpenAI LLM Integration** (`adapters/llm/openai_llm.py`)
   - Fully functional adapter using GPT-4.1 (or GPT-3.5)
   - Streaming support implemented
   - Async/await pattern for performance
   - Error handling and logging
   
2. **Supabase Vector Store** (`adapters/vectorstore/supabase_store.py`)
   - pgvector integration complete
   - Semantic search with cosine similarity
   - Metadata filtering support
   - Upsert and query operations ready

3. **Complete RAG Pipeline** (`services/chat_orchestrator.py`)
   - 10-step orchestration pipeline
   - Retrieval → Grounding → Generation → Postprocessing
   - Multi-turn conversation memory
   - Citation extraction

4. **Chat API Endpoint** (`api/v1/routes_chat.py`)
   - `POST /api/v1/chat/message` - **READY TO USE**
   - Authentication + rate limiting
   - Full request/response validation

#### ⚠️ What's Missing (Phase 1.D):

**Knowledge Base Content!** The vector store is **empty**.

The LLM and Supabase are fully integrated, but there's **no legal content** to retrieve. Think of it like:
- ✅ Your search engine is built
- ✅ Your database is set up
- ❌ Your database has no documents indexed yet

---

### Q2: Did we miss integrating LLM and Supabase?

**Answer**: **No, nothing was missed!** Everything is integrated properly.

Here's the **complete integration flow**:

```
User Request → Chat API → Chat Orchestrator → RAG Pipeline
                                ↓
                    ┌───────────┴────────────┐
                    ↓                        ↓
            Retrieval Pipeline      Generation Pipeline
                    ↓                        ↓
            Supabase Vector Store    OpenAI LLM Adapter
                    ↓                        ↓
              (EMPTY NOW!)           (READY TO USE!)
```

**The integration chain is complete**, but the knowledge base is empty.

---

### Q3: Database Migrations - Alembic vs Terraform?

**Answer**: **Currently NEITHER**, but here's what the project intends:

#### Current Situation:
- **No Alembic migrations** (no `alembic.ini` or `migrations/` folder)
- **Supabase schema not in Terraform yet** (`infra/supabase/` is empty)
- Schema is managed **manually in Supabase dashboard**

#### What the Project Plans (from `ImplementationSequence.md`):

**Phase 8 (Infrastructure as Code)** will add:
```
infra/terraform/modules/
  └─ supabase_integration/  # Database schema as code
```

#### Recommended Approach for This Project:

**Option 1: Supabase Schema Files** (Simplest, matches current architecture)
```
infra/supabase/
  ├─ schema.sql              # CREATE TABLE statements
  ├─ migrations/
  │  ├─ 001_initial_schema.sql
  │  ├─ 002_add_conversations.sql
  │  └─ 003_add_feedback.sql
  └─ seed.sql                # Sample data
```

**Why this approach?**
- Supabase has built-in migration tooling
- Simpler than Alembic for cloud-hosted Postgres
- Matches the project's cloud-native approach
- Can be applied via Supabase CLI or Terraform

**Option 2: Alembic** (Traditional, more control)
- Requires direct Postgres connection
- More overhead for a cloud-hosted DB
- Better for complex migrations

**Recommendation**: Use **Supabase schema files** + **Terraform** in Phase 8 for infrastructure as code.

---

## Current Project Status

### ✅ Completed Phases:

#### **Phase 0 - Scaffold & Contracts**
- Folder structure ✅
- Core config and logging ✅
- Health endpoints ✅
- Adapter interfaces ✅

#### **Phase 1.A - Authentication**
- Anonymous session creation ✅
- JWT token generation/validation ✅
- Session management service ✅
- Auth middleware ✅

#### **Phase 1.B - Core Infrastructure**
- OpenAI LLM adapter ✅
- OpenAI embeddings adapter ✅
- Supabase vector store adapter ✅
- LangChain memory adapter ✅
- All 5 pipeline services ✅
  - Conversation
  - Retrieval
  - Grounding
  - Generation
  - Postprocessing

#### **Phase 1.C - Chat API** ✅ **JUST COMPLETED!**
- Chat message endpoint ✅
- Request/response schemas ✅
- Chat orchestrator ✅
- Rate limiting ✅
- Multi-turn conversation ✅
- Error handling ✅

### 🚧 Current Phase:

#### **Phase 1.D - Knowledge Base Setup** ⬅️ **YOU ARE HERE**

**What needs to be done:**
1. Create `kb/ingest/sync_to_vectorstore.py` script
2. Add 20-30 Philippine Labor Code sections to `kb/docs/`
3. Implement chunking logic (100-300 words per chunk)
4. Generate embeddings for each chunk
5. Upload chunks to Supabase vector store
6. Add metadata with canonical URLs (Lawphil, DOLE, NLRC)
7. Test retrieval accuracy

**Once complete**: The LLM will have legal content to work with! 🎯

---

## How to Test the LLM (Even Without KB Content)

You can test the LLM **right now** even though the KB is empty:

### Method 1: Direct LLM Test (No API)

Create a test script:

```python
# test_llm_direct.py
import asyncio
from adapters.llm.openai_llm import OpenAILLM, Message
from core.config import Settings

async def test_llm():
    settings = Settings()  # Loads from .env
    llm = OpenAILLM(settings=settings)
    
    messages = [
        Message(role="system", content="You are a helpful assistant."),
        Message(role="user", content="What is labor law?")
    ]
    
    response = await llm.generate(messages)
    print(f"LLM Response: {response.content}")
    print(f"Tokens: {response.usage}")

asyncio.run(test_llm())
```

Run it:
```powershell
python test_llm_direct.py
```

### Method 2: Test Chat API (Returns Empty KB Warning)

Start the server:
```powershell
python -m uvicorn app.main:app --reload
```

Test the chat endpoint:
```powershell
# First, create a session
$session = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/session" -Method POST -ContentType "application/json" -Body '{}'

# Then send a chat message
$headers = @{
    "Authorization" = "Bearer $($session.token)"
    "Content-Type" = "application/json"
}

$body = @{
    message = "What are my rights as an employee?"
    language = "en"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/v1/chat/message" -Method POST -Headers $headers -Body $body
```

**Expected result**: 
- ✅ LLM will respond (proving integration works)
- ⚠️ Response will say "I don't have specific legal information" (because KB is empty)
- ✅ Response structure will be complete with citations[], suggestions[], metadata

---

## Database Schema - What Exists Now

### Current Tables (must exist in Supabase):

```sql
-- This is what SHOULD be in your Supabase database
-- Check if these exist in Supabase Dashboard > Table Editor

-- 1. Sessions table (for auth)
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- 2. Vector embeddings table (for KB)
CREATE TABLE labor_law_embeddings (
    id VARCHAR(255) PRIMARY KEY,
    content TEXT NOT NULL,
    embedding VECTOR(1536),  -- Requires pgvector extension
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Add vector similarity search index
CREATE INDEX labor_law_embeddings_embedding_idx 
ON labor_law_embeddings 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

### Tables Coming in Phase 1.1 (Conversation Management):

```sql
-- 3. Conversations table
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) REFERENCES sessions(session_id),
    title VARCHAR(500),
    language VARCHAR(10),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    archived BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMPTZ
);

-- 4. Messages table
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,  -- 'user' or 'assistant'
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Next Steps - Phase 1.D Roadmap

### Step 1: Verify Database Schema
```powershell
# Check if tables exist in Supabase
# Go to: Supabase Dashboard > Table Editor
# Verify: sessions, labor_law_embeddings tables exist
```

### Step 2: Create KB Ingestion Script

File: `kb/ingest/sync_to_vectorstore.py`

```python
"""
Knowledge Base ingestion script.

Chunks legal documents, generates embeddings, and uploads to Supabase.
"""
import asyncio
from pathlib import Path

# This will be your Phase 1.D implementation
```

### Step 3: Add Legal Documents

Directory: `kb/docs/`

```
kb/docs/
  ├─ labor_code_book1.txt        # Preliminary Matters
  ├─ labor_code_book2.txt        # Human Resources Development
  ├─ labor_code_book3.txt        # Conditions of Employment
  ├─ labor_code_book4.txt        # Health, Safety & Social Welfare
  ├─ labor_code_book5.txt        # Labor Relations
  └─ labor_code_book6.txt        # Post-Employment
```

### Step 4: Implement Chunking

```python
def chunk_document(content: str, chunk_size: int = 200) -> list[str]:
    """Split document into semantic chunks."""
    # Word-based chunking with overlap
    # Preserve article boundaries
    # ~100-300 words per chunk
```

### Step 5: Generate Embeddings

```python
from adapters.embeddings.openai_embed import OpenAIEmbeddings

embeddings_adapter = OpenAIEmbeddings(settings=settings)
embedding_vector = await embeddings_adapter.embed_text(chunk_text)
```

### Step 6: Upload to Supabase

```python
from adapters.vectorstore.supabase_store import SupabaseVectorStore

documents = [
    Document(
        id="labor_code_art_1_chunk_0",
        content=chunk_text,
        embedding=embedding_vector,
        metadata={
            "source": "Labor Code",
            "article": "Article 1",
            "url": "https://www.lawphil.net/statutes/pdas/pd1974/pd_442_1974.html",
            "book": "1"
        }
    )
]

await vectorstore.upsert(documents)
```

### Step 7: Test Retrieval

```python
# Test query
query = "What are the grounds for termination?"
query_embedding = await embeddings_adapter.embed_text(query)
results = await vectorstore.query(query_embedding, limit=5)

for result in results:
    print(f"Score: {result.score}")
    print(f"Content: {result.document.content}")
    print(f"Source: {result.document.metadata['source']}")
```

---

## Environment Setup Checklist

### ✅ What You Should Have:

1. **`.env` file** with these values:
   ```bash
   OPENAI_API_KEY=sk-...                    # Your OpenAI key
   SUPABASE_URL=https://....supabase.co     # Your Supabase URL
   SUPABASE_KEY=eyJ...                      # Service role key
   JWT_SECRET_KEY=...                       # Random secret
   ```

2. **Supabase Project** with:
   - ✅ pgvector extension enabled
   - ✅ `sessions` table created
   - ✅ `labor_law_embeddings` table created
   - ✅ Vector index created

3. **Python Environment**:
   ```powershell
   # Check if installed
   pip list | Select-String "openai|supabase|fastapi|pydantic"
   ```

---

## Common Confusion Points Explained

### 1. "Why is the KB ingestion separate from the API?"

**Answer**: They serve different purposes:
- **API** = Runtime service (handles user requests)
- **KB ingestion** = One-time setup/maintenance task (populate database)

Think of it like:
- API = Restaurant serving customers
- KB ingestion = Stocking the kitchen with ingredients

### 2. "Can I test the LLM without the KB?"

**Answer**: **YES!** The LLM works independently:
- LLM = Brain that can answer general questions
- KB = Memory bank with specific legal facts

Without KB:
- LLM can still chat (using its training data)
- But won't cite specific Philippine Labor Code articles
- Won't have authoritative legal sources

### 3. "Do I need Alembic for migrations?"

**Answer**: **Not necessarily**:
- **Alembic** = Traditional Flask/Django approach
- **Supabase** = Has built-in migration tooling
- **This project** = Will use Terraform + SQL files (Phase 8)

For now: Create tables manually in Supabase dashboard.

### 4. "Why are there so many pipeline services?"

**Answer**: **Separation of concerns** (clean architecture):
- `ConversationPipeline` = Manages chat history
- `RetrievalPipeline` = Searches knowledge base
- `GroundingPipeline` = Builds context-aware prompts
- `GenerationPipeline` = Calls LLM
- `PostprocessPipeline` = Formats response

Each service has **one job**, making testing/debugging easier.

---

## Troubleshooting Guide

### Issue: "Can't connect to Supabase"

**Check**:
```powershell
# Test Supabase connection
python -c "from supabase import create_client; from core.config import Settings; s = Settings(); c = create_client(s.supabase_url, s.supabase_key); print(c.table('sessions').select('*').limit(1).execute())"
```

### Issue: "OpenAI API error"

**Check**:
```powershell
# Test OpenAI connection
python -c "from openai import OpenAI; from core.config import Settings; s = Settings(); c = OpenAI(api_key=s.openai_api_key); print(c.models.list())"
```

### Issue: "Vector search returns nothing"

**Check**:
```sql
-- In Supabase SQL Editor
SELECT COUNT(*) FROM labor_law_embeddings;
-- Should return > 0 after Phase 1.D
-- Currently returns 0 (empty KB)
```

---

## Summary - Where You Are

### ✅ What Works Now:
1. **Authentication system** - Create sessions, validate tokens
2. **Chat API endpoint** - Send messages, get responses
3. **LLM integration** - OpenAI GPT-4 ready to use
4. **Vector store connection** - Supabase connected (but empty)
5. **Complete RAG pipeline** - All components wired together

### ❌ What's Missing:
1. **Knowledge base content** - No legal documents indexed
2. **Database schema** - Tables need to be created in Supabase
3. **Migration management** - No formal migration system yet (Phase 8)

### 🎯 Your Next Milestone:
**Phase 1.D**: Implement KB ingestion to populate the vector store with Philippine Labor Code content.

**Estimated Time**: 3-4 hours  
**Difficulty**: Medium (mostly data preparation)

---

## Quick Start Testing Guide

### Test 1: Health Check
```powershell
Invoke-RestMethod http://localhost:8000/api/v1/healthz
# Expected: {"status": "healthy"}
```

### Test 2: Create Session
```powershell
Invoke-RestMethod -Uri http://localhost:8000/api/v1/auth/session -Method POST -ContentType "application/json" -Body '{}'
# Expected: {"token": "eyJ...", "sessionId": "...", "expiresAt": "..."}
```

### Test 3: Send Chat Message
```powershell
# Use token from Test 2
$headers = @{"Authorization" = "Bearer YOUR_TOKEN_HERE"}
$body = '{"message": "Hello, can you help me?", "language": "en"}' 
Invoke-RestMethod -Uri http://localhost:8000/api/v1/chat/message -Method POST -Headers $headers -Body $body -ContentType "application/json"
# Expected: Full response with content, citations (empty), suggestions, metadata
```

---

## Resources

### Documentation Files:
- `docs/BACKEND_API_SPECIFICATIONS.md` - Complete API reference
- `docs/PHASE_1C_COMPLETION.md` - What was just completed
- `docs/PHASE_1C_SUMMARY.md` - Quick reference
- `ImplementationSequence.md` - Full project roadmap

### Key Code Files:
- `adapters/llm/openai_llm.py` - LLM integration
- `adapters/vectorstore/supabase_store.py` - Vector DB
- `services/chat_orchestrator.py` - RAG pipeline
- `api/v1/routes_chat.py` - Chat endpoint

### Next Phase Prep:
- `kb/ingest/` - Where ingestion script goes
- `kb/docs/` - Where legal documents go
- `infra/supabase/` - Where schema files will go (Phase 8)

---

## Need Help?

If you're stuck, check these in order:

1. **Verify environment**: `.env` file has all required keys
2. **Check logs**: Look at uvicorn output for errors
3. **Test components**: Use direct adapter tests (see examples above)
4. **Review docs**: API specs have detailed examples
5. **Check Supabase**: Verify tables exist in dashboard

---

**Welcome aboard! You're in great shape - the hard integration work is done.** 🚀

Next step: Phase 1.D - Let's add some legal knowledge to this brain! 🧠⚖️
