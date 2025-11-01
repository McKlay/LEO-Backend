# LEO Backend - Current Architecture State

**Date**: January 2025  
**Status**: Phase 1.C Complete, Phase 1.D Ready

---

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT APPLICATION                        │
│                     (Frontend - Not Built Yet)                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ HTTP/REST API
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                      FASTAPI APPLICATION                         │
│                     (LEO-Backend - YOU ARE HERE)                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────────┐   │
│  │  Auth Routes   │  │  Chat Routes   │  │ Health Routes   │   │
│  │  ✅ WORKING    │  │  ✅ WORKING    │  │  ✅ WORKING     │   │
│  └────────┬───────┘  └────────┬───────┘  └────────┬────────┘   │
│           │                   │                    │             │
│           ↓                   ↓                    ↓             │
│  ┌────────────────────────────────────────────────────────┐    │
│  │          SESSION SERVICE & AUTH MIDDLEWARE             │    │
│  │                    ✅ WORKING                           │    │
│  └────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ↓                                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              CHAT ORCHESTRATOR (RAG PIPELINE)          │    │
│  │                    ✅ WORKING                           │    │
│  │                                                          │    │
│  │  Step 1: Add user message to conversation              │    │
│  │  Step 2: Check vague query → clarify if needed         │    │
│  │  Step 3: Retrieve from knowledge base ⚠️ EMPTY KB      │    │
│  │  Step 4: Get conversation history                       │    │
│  │  Step 5: Build grounded prompt                          │    │
│  │  Step 6: Generate LLM response ✅ LLM READY             │    │
│  │  Step 7: Extract citations                              │    │
│  │  Step 8: Post-process response                          │    │
│  │  Step 9: Add assistant message                          │    │
│  │  Step 10: Build final response                          │    │
│  └──────────┬─────────────┬──────────────┬─────────────────┘    │
│             │             │              │                       │
│             ↓             ↓              ↓                       │
│  ┌─────────────┐ ┌─────────────┐ ┌──────────────┐              │
│  │ Retrieval   │ │  Grounding  │ │  Generation  │              │
│  │  Pipeline   │ │   Pipeline  │ │   Pipeline   │              │
│  │ ✅ WORKING  │ │ ✅ WORKING  │ │ ✅ WORKING   │              │
│  └──────┬──────┘ └──────┬──────┘ └──────┬───────┘              │
│         │               │               │                       │
│         ↓               │               ↓                       │
│  ┌─────────────┐        │        ┌──────────────┐              │
│  │ Conversation│        │        │ Postprocess  │              │
│  │  Pipeline   │        │        │   Pipeline   │              │
│  │ ✅ WORKING  │        │        │ ✅ WORKING   │              │
│  └──────┬──────┘        │        └──────────────┘              │
│         │               │                                       │
└─────────┼───────────────┼───────────────────────────────────────┘
          │               │
          ↓               ↓
┌─────────────────────────────────────────────────────────────────┐
│                      ADAPTER LAYER (I/O)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────────┐   │
│  │ OpenAI LLM     │  │   Embeddings   │  │  Vector Store   │   │
│  │   Adapter      │  │    Adapter     │  │    Adapter      │   │
│  │ ✅ READY       │  │  ✅ READY      │  │  ✅ READY       │   │
│  └────────┬───────┘  └────────┬───────┘  └────────┬────────┘   │
│           │                   │                    │             │
│           ↓                   ↓                    ↓             │
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────────┐   │
│  │  LangChain     │  │  Translation   │  │  Moderation     │   │
│  │    Memory      │  │    Adapter     │  │    Adapter      │   │
│  │ ✅ READY       │  │ ⏸️ PHASE 3     │  │ ⏸️ PHASE 5     │   │
│  └────────────────┘  └────────────────┘  └─────────────────┘   │
│                                                                   │
└───────────┬────────────┬──────────────┬──────────────────────────┘
            │            │              │
            ↓            ↓              ↓
┌────────────────┐ ┌─────────────┐ ┌──────────────────────────┐
│   OPENAI API   │ │  SUPABASE   │ │  GOOGLE CLOUD APIs       │
│  ✅ CONNECTED  │ │ ✅ CONNECTED│ │  ⏸️ NOT CONFIGURED YET   │
└────────────────┘ └─────┬───────┘ └──────────────────────────┘
                         │
                         ↓
              ┌─────────────────────┐
              │  POSTGRESQL + PGVECTOR │
              │   ✅ CONNECTED          │
              │   ⚠️ EMPTY TABLES      │
              └─────────────────────┘
```

---

## Component Status Legend

| Symbol | Status | Meaning |
|--------|--------|---------|
| ✅ | WORKING | Fully implemented and functional |
| ⚠️ | EMPTY/INCOMPLETE | Code works but missing data |
| ⏸️ | FUTURE PHASE | Not implemented yet (planned) |
| ❌ | BROKEN | Not working, needs fixing |

---

## Current Integration Status

### ✅ Fully Integrated & Working:

1. **FastAPI Application**
   - Health endpoints (`/api/v1/healthz`, `/api/v1/readyz`)
   - Auth endpoints (`/api/v1/auth/session`)
   - Chat endpoints (`/api/v1/chat/message`, `/api/v1/chat/conversations/{id}`)

2. **Authentication System**
   - Anonymous session creation
   - JWT token generation/validation
   - Auth middleware for protected routes
   - Session persistence in Supabase

3. **OpenAI Integration**
   - LLM adapter (GPT-4/GPT-3.5)
   - Embeddings adapter (text-embedding-3-small)
   - Async/await support
   - Streaming capability (not yet used)
   - Error handling and retry logic

4. **Supabase Integration**
   - Database connection
   - Vector store adapter (pgvector)
   - Semantic search queries
   - Metadata filtering
   - Session storage

5. **RAG Pipeline**
   - All 5 pipeline services implemented
   - Conversation memory management
   - Retrieval with semantic search
   - Context grounding
   - LLM generation
   - Response post-processing

6. **Chat Orchestrator**
   - 10-step pipeline coordination
   - Multi-turn conversation support
   - Vague query detection
   - Citation extraction
   - Suggested actions generation

### ⚠️ Integrated But Missing Data:

1. **Knowledge Base (Vector Store)**
   - **Status**: Adapter working, database empty
   - **Issue**: No legal documents indexed yet
   - **Fix**: Phase 1.D - Add Philippine Labor Code content
   - **Impact**: Chat works, but has no legal knowledge to cite

2. **Database Tables**
   - **Status**: Some tables may not exist in Supabase
   - **Issue**: Manual table creation needed
   - **Fix**: Create tables via Supabase dashboard or SQL
   - **Required Tables**:
     ```sql
     - sessions (for auth)
     - labor_law_embeddings (for KB - EXISTS BUT EMPTY)
     - conversations (Phase 1.1 - not needed yet)
     - messages (Phase 1.1 - not needed yet)
     - feedback (Phase 1.2 - not needed yet)
     ```

### ⏸️ Not Yet Integrated (Future Phases):

1. **Translation** (Phase 3)
   - Google Cloud Translation API
   - Language detection (FastText)
   - Multilingual output

2. **Intent Classification** (Phase 4)
   - DistilBERT classifier
   - Philippine labor law taxonomy
   - Retrieval enhancement

3. **Moderation** (Phase 5)
   - OpenAI moderation API
   - UPL (Unauthorized Practice of Law) detection
   - Content filtering

4. **Legal Aid Referrals** (Phase 6)
   - Google Maps Places API
   - Location-based services
   - Legal aid directory

---

## Data Flow - Current vs. Complete

### Current Data Flow (Phase 1.C):

```
1. User sends message
2. Auth middleware validates JWT token ✅
3. Rate limiter checks request limit ✅
4. Chat orchestrator starts pipeline ✅
5. Retrieval queries vector store ⚠️ Returns empty (no KB content)
6. Grounding builds prompt with empty context ⚠️
7. LLM generates response ✅ (using only conversation history)
8. Postprocess extracts citations ⚠️ (none to extract)
9. Response returned to user ✅ (generic answer, no citations)
```

**Result**: Chat works, but gives generic answers without legal citations.

### Complete Data Flow (After Phase 1.D):

```
1. User sends message
2. Auth middleware validates JWT token ✅
3. Rate limiter checks request limit ✅
4. Chat orchestrator starts pipeline ✅
5. Retrieval queries vector store ✅ Returns relevant Labor Code chunks
6. Grounding builds prompt with legal context ✅
7. LLM generates grounded response ✅ (cites specific articles)
8. Postprocess extracts citations ✅ (with URLs)
9. Response returned to user ✅ (authoritative answer with citations)
```

**Result**: Chat provides accurate legal information with citations!

---

## Database Schema Status

### Existing Schema (Must Be Created):

```sql
-- Table 1: Sessions (for authentication)
-- STATUS: ✅ Should exist from Phase 1.A
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Table 2: Vector Embeddings (for knowledge base)
-- STATUS: ⚠️ Exists but EMPTY (no rows)
CREATE TABLE labor_law_embeddings (
    id VARCHAR(255) PRIMARY KEY,
    content TEXT NOT NULL,
    embedding VECTOR(1536),  -- OpenAI embedding dimension
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for vector similarity search
CREATE INDEX labor_law_embeddings_embedding_idx 
ON labor_law_embeddings 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

### Future Schema (Phase 1.1+):

```sql
-- Coming in Phase 1.1 - Conversation Management
CREATE TABLE conversations (...);
CREATE TABLE messages (...);

-- Coming in Phase 1.2 - Feedback System
CREATE TABLE feedback_ratings (...);
CREATE TABLE feedback_flags (...);
```

---

## Migration Strategy

### Current Approach: Manual (Temporary)

**For Development**:
1. Create tables via Supabase Dashboard > SQL Editor
2. Copy SQL from schema files
3. Execute manually

**Pros**: Simple, works for initial development
**Cons**: Not reproducible, error-prone, not version-controlled

### Planned Approach: Infrastructure as Code (Phase 8)

**Directory Structure**:
```
infra/supabase/
  ├─ schema.sql              # Complete schema
  ├─ migrations/
  │  ├─ 001_initial_schema.sql
  │  ├─ 002_add_conversations.sql
  │  └─ 003_add_feedback.sql
  └─ seed.sql                # Sample data

infra/terraform/modules/supabase_init/
  └─ main.tf                 # Terraform to apply migrations
```

**Deployment**:
```bash
# Apply via Supabase CLI
supabase db push

# Or via Terraform
terraform apply -target=module.supabase_init
```

**Pros**: Version-controlled, reproducible, automated
**Cons**: More setup, requires Phase 8 implementation

### Recommendation for Now:

**Use SQL files + manual execution**:

1. Create `infra/supabase/schema.sql` with all CREATE TABLE statements
2. Execute in Supabase Dashboard when needed
3. Version control the SQL files
4. Migrate to automated approach in Phase 8

---

## Testing Strategy by Component

### 1. Test OpenAI LLM (Direct)
```python
# test_openai.py
import asyncio
from adapters.llm.openai_llm import OpenAILLM, Message
from core.config import Settings

async def main():
    settings = Settings()
    llm = OpenAILLM(settings=settings)
    
    messages = [
        Message(role="user", content="What is the minimum wage in the Philippines?")
    ]
    
    response = await llm.generate(messages)
    print(f"✅ LLM Response: {response.content}")
    print(f"📊 Tokens Used: {response.usage}")

asyncio.run(main())
```

### 2. Test Supabase Connection (Direct)
```python
# test_supabase.py
from supabase import create_client
from core.config import Settings

settings = Settings()
client = create_client(settings.supabase_url, settings.supabase_key)

# Test connection
result = client.table('sessions').select('count').execute()
print(f"✅ Supabase connected. Session count: {result}")

# Test vector store (will be empty)
result = client.table('labor_law_embeddings').select('count').execute()
print(f"⚠️ KB documents: {result} (should be 0 until Phase 1.D)")
```

### 3. Test Chat API (Integration)
```powershell
# Step 1: Start server
python -m uvicorn app.main:app --reload

# Step 2: Create session
$session = Invoke-RestMethod -Uri http://localhost:8000/api/v1/auth/session -Method POST -ContentType "application/json" -Body '{}'

# Step 3: Send message
$headers = @{"Authorization" = "Bearer $($session.token)"}
$body = '{"message": "What are my rights as an employee?", "language": "en"}' 
Invoke-RestMethod -Uri http://localhost:8000/api/v1/chat/message -Method POST -Headers $headers -Body $body -ContentType "application/json"
```

**Expected Result**:
```json
{
  "messageId": "uuid-here",
  "conversationId": "uuid-here",
  "content": "Generic response (no specific legal citations)",
  "citations": [],  // ⚠️ Empty until Phase 1.D
  "suggestions": [
    {
      "id": "1",
      "type": "info",
      "label": "Learn more about employee rights",
      "data": {...}
    }
  ],
  "metadata": {
    "language": "en",
    "processingTime": 2.5,
    "tokensUsed": 150,
    "model": "gpt-4-turbo-preview"
  }
}
```

---

## Phase 1.D - What Happens Next

### Goal: Populate Knowledge Base

**Input**: Philippine Labor Code text documents
**Output**: Indexed embeddings in Supabase vector store

### Implementation Steps:

```
kb/ingest/sync_to_vectorstore.py
  │
  ├─ 1. Load legal documents from kb/docs/
  │     └─ labor_code_book1.txt, labor_code_book2.txt, etc.
  │
  ├─ 2. Chunk documents
  │     └─ Split into 100-300 word chunks
  │     └─ Preserve article boundaries
  │     └─ Add metadata (source, article, book, url)
  │
  ├─ 3. Generate embeddings
  │     └─ Use OpenAI text-embedding-3-small
  │     └─ Create 1536-dimension vectors
  │
  ├─ 4. Upload to Supabase
  │     └─ Upsert to labor_law_embeddings table
  │     └─ ~500-1000 chunks for 20-30 sections
  │
  └─ 5. Verify retrieval
        └─ Test queries
        └─ Check relevance scores
        └─ Validate citations
```

### After Phase 1.D Completion:

**What Changes**:
- Vector store has ~500-1000 document chunks ✅
- Retrieval returns relevant legal content ✅
- LLM responses cite specific Labor Code articles ✅
- Citations include canonical URLs ✅
- Suggested actions are context-aware ✅

**What Stays the Same**:
- API endpoints (no changes)
- Chat orchestrator (works with populated KB)
- All adapters (already integrated)

---

## Summary - Current State

### ✅ What You Have:
- Complete FastAPI application with working endpoints
- Fully integrated OpenAI LLM (ready to use)
- Fully integrated Supabase vector store (connected but empty)
- Complete RAG pipeline (all services implemented)
- Authentication and session management (working)
- Rate limiting and error handling (working)

### ⚠️ What's Missing:
- Knowledge base content (no legal documents indexed)
- Database tables (may need manual creation)
- Formal migration system (planned for Phase 8)

### 🎯 What's Next:
- **Phase 1.D**: Add Philippine Labor Code content to knowledge base
- **Estimated Time**: 3-4 hours
- **Difficulty**: Medium (data preparation + chunking logic)

---

**You're in excellent shape! The hard integration work is done. Now we just need to feed the knowledge base.** 🚀
