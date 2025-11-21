# Phase 1.0.5 Implementation Checklist

**Goal**: Multi-strategy RAG with streaming, smart clarification, and dual-table retrieval  
**Status**: KB Ingestion Complete ✅ | Retrieval Update & Testing Next 🔴  
**Updated**: November 20, 2025

---

## 📍 Current Progress

### ✅ Completed Components
- **Query Analysis**: GPT-4o-mini with smart clarification, concept extraction
- **Database Schema**: HNSW indexes, connection pooling, embedding LRU cache
- **Streaming**: SSE streaming with GPT-4.1, time-to-first-token <3.5s
- **KB Infrastructure**: Incremental tracker, LLM chunking, source management
- **Data Ingestion**: PD-No-442 fully ingested (65 sections + sub-chunks)

### 🎯 Next Steps (Immediate)

#### 1. Update Retrieval Logic (2-3h) 🔴 **CRITICAL - START HERE**
Query both `labor_law_sections` AND `labor_law_chunks` tables

#### 2. Accuracy Testing (2-3h)
Test with 20 queries, target 90% accuracy

#### 3. Performance Testing (1h)
Validate latency targets: <9s clear, <1.5s vague, <3.5s TTFT

#### 4. Integration Tests (1-2h)
Update and verify all test suites passing

#### 5. Frontend Connection (2-3h)
End-to-end user flow validation

**Estimated Time**: 8-12 hours (1-1.5 days)  
**No additional costs** (ingestion already complete)

---

## 🚀 Detailed Implementation Steps

### Step 1: Update Retrieval Logic 🔴 **START HERE**

**Objective**: Enable dual-table querying (sections + chunks) for better coverage

**Files to Modify**:
- `adapters/vectorstore/supabase_store.py`
- `services/pipeline/retrieval.py`

**Tasks**:

#### A. Add Dual-Table Query Method (1-1.5h)
```python
# In adapters/vectorstore/supabase_store.py

async def query_with_chunks(
    self,
    query_embedding: List[float],
    limit: int = 10,
    similarity_threshold: float = 0.7
) -> List[Dict[str, Any]]:
    """
    Query both labor_law_sections and labor_law_chunks.
    
    Strategy:
    1. Query sections table (get top-level articles)
    2. Query chunks table (get granular sub-sections)
    3. Merge and deduplicate results
    4. Rank by relevance (prefer chunks > sections for specific queries)
    
    Returns: Unified list of results with source metadata
    """
```

**Implementation Checklist**:
- [x] Add `query_with_chunks()` method to `SupabaseVectorStore`
- [x] Implement parallel queries using `asyncio.gather()`
- [x] Add result merging logic (combine sections + chunks)
- [x] Implement deduplication (if chunk exists, prefer over parent section)
- [x] Add ranking algorithm:
  - Chunks with >0.85 similarity: Priority 1
  - Sections with >0.80 similarity: Priority 2
  - Chunks with >0.75 similarity: Priority 3
  - Sections with >0.70 similarity: Priority 4
- [x] Add metadata enrichment (source title, article number, chunk context)
- [x] Add logging for retrieval strategy used

#### B. Update Retrieval Service (0.5-1h)
```python
# In services/pipeline/retrieval.py

async def smart_retrieve_with_chunks(
    query: str,
    analysis: QueryAnalysis,
    limit: int = 10
) -> List[Document]:
    """
    Enhanced retrieval using dual-table strategy.
    
    Routes:
    1. Direct article lookup → labor_law_sections
    2. Keyword search → both tables
    3. Semantic search → query_with_chunks()
    """
```

**Implementation Checklist**:
- [x] Update `smart_retrieve()` to call `query_with_chunks()`
- [x] Add chunk-aware result formatting
- [x] Update logging to show sections vs chunks retrieved
- [x] Add fallback to sections-only if chunks query fails

#### C. Testing (0.5-1h)
- [x] Unit test `query_with_chunks()` with mock data
- [x] Test deduplication logic (parent section + child chunk)
- [x] Test ranking algorithm with varying similarity scores
- [x] Fix existing test failures (updated mocks for query_with_chunks)
- [x] Integration test script created for real data (PD-851, RA-10362, COVID)

**Exit Criteria**:
- ✅ Dual-table query works without errors
- ✅ Results include both sections and chunks
- ✅ Deduplication prevents redundant results
- ✅ Ranking prioritizes most relevant content type
- ✅ 30/30 unit tests passing (excluding query_analysis separate issues)
- ⏳ Integration tests with real DB pending manual run

---

## ✅ Step 1 Complete Summary

**Implementation Status**: COMPLETE  
**Unit Tests**: 30/30 passing (query_analysis tests have separate async mock issues)  
**Files Modified**: 3 files  
**Files Created**: 2 test files  
**Time Taken**: ~3 hours

### Key Changes
1. Added `query_with_chunks()` method - queries both tables in parallel
2. Updated `smart_retrieve()` to use dual-table semantic search
3. Fixed query analysis timeout (5s → 10s)
4. Created comprehensive tests for real ingested data

### Next Action
Run integration tests with backend:
```bash
python tests/integration/test_dual_table_ingested.py
```

---

## Step 2: Accuracy Testing (2-3h)

**Objective**: Validate 90%+ accuracy on diverse query set

**Test Query Categories** (20 queries total):

#### Direct Article Queries (4 queries)
- [ ] "What does Article 82 say?"
- [ ] "Article 97 definition of wages"
- [ ] "Show me Article 111"
- [ ] "Article 157 emergency overtime"

**Expected**: Direct lookup to `labor_law_sections`, exact article returned

#### Specific Calculation Queries (5 queries)
- [ ] "How to calculate overtime pay?"
- [ ] "Night shift differential computation formula"
- [ ] "13th month pay calculation for resigned employees"
- [ ] "How much is holiday pay on regular holidays?"
- [ ] "Service incentive leave conversion formula"

**Expected**: Chunks retrieved with formulas/tables, 3+ citations

#### Concept/Topic Queries (5 queries)
- [ ] "What are the types of leaves in the Philippines?"
- [ ] "Employee benefits under labor code"
- [ ] "Maternity leave entitlements"
- [ ] "Termination pay computation"
- [ ] "Rest day requirements"

**Expected**: Mixed sections + chunks, 4+ citations, comprehensive answer

#### Vague/Clarification Queries (4 queries)
- [ ] "Tell me about leave"
- [ ] "What about pay?"
- [ ] "I have a question about work hours"
- [ ] "Can you help with employee rights?"

**Expected**: Smart clarification triggered, 3-4 follow-up questions

#### Multi-turn Conversations (2 queries)
- [ ] "What is overtime pay?" → "How is it calculated?" → "What if I work on a holiday?"
- [ ] "Tell me about maternity leave" → "How long is it?" → "Do I get paid?"

**Expected**: Context-aware responses, no repeated clarifications

**Accuracy Metrics**:
- [ ] 18/20 queries (90%) return correct information
- [ ] 15/16 clear queries provide 3+ relevant citations
- [ ] 4/4 vague queries trigger clarification
- [ ] 2/2 multi-turn flows maintain context
- [ ] 0 hallucinations (all answers grounded in retrieved docs)

**Testing Process**:
```bash
# Create test script
python scripts/test_accuracy.py --queries tests/data/accuracy_test_queries.json
```

- [ ] Create `tests/data/accuracy_test_queries.json` with 20 queries
- [ ] Create `scripts/test_accuracy.py` to run batch queries
- [ ] Manually review each response for correctness
- [ ] Document failures and root causes
- [ ] Fix retrieval/ranking if accuracy <90%

**Exit Criteria**:
- ✅ 90%+ accuracy on all query types
- ✅ Clear queries: 3+ citations, grounded answers
- ✅ Vague queries: specific follow-ups
- ✅ Multi-turn: context maintained
- ✅ Zero hallucinations

---

### Step 3: Performance Testing (1h)

**Objective**: Validate latency targets

**Metrics to Test**:

| Metric | Target | Test Method |
|--------|--------|-------------|
| Clear Query Latency | <9s | 10 clear queries, avg response time |
| Vague Query Latency | <1.5s | 10 vague queries, avg clarification time |
| Time-to-First-Token | <3.5s | 10 streaming queries, measure first chunk |
| Retrieval Time | <2.5s | 10 vector searches, avg query time |
| Cache Hit Rate | >30% | 20 queries, 6+ repeated embeddings |

**Test Script**:
```bash
# Run performance benchmarks
python scripts/test_performance.py --iterations 10
```

**Implementation**:
- [ ] Create `scripts/test_performance.py`
  - [ ] Measure end-to-end latency (query → final response)
  - [ ] Measure retrieval latency (embedding + vector search)
  - [ ] Measure time-to-first-token for streaming
  - [ ] Track cache hits/misses
  - [ ] Output results as JSON + summary table

- [ ] Run 10 iterations for each metric
- [ ] Calculate mean, median, p95, p99
- [ ] Compare against Phase 1.E baseline (12.4s avg)

**Expected Results**:
```
Clear Query Latency:     8.2s avg (target <9s) ✅
Vague Query Latency:     1.1s avg (target <1.5s) ✅
Time-to-First-Token:     2.9s avg (target <3.5s) ✅
Retrieval Time:          1.8s avg (target <2.5s) ✅
Cache Hit Rate:          34% (target >30%) ✅
```

**Exit Criteria**:
- ✅ All 5 metrics meet or exceed targets
- ✅ No performance regression from Phase 1.E
- ✅ Streaming consistently delivers first token <3.5s

---

### Step 4: Integration Tests (1-2h)

**Objective**: Ensure all test suites pass with new retrieval logic

**Test Files to Update**:

#### A. Update Existing Tests
- [ ] `tests/integration/test_chat_e2e.py`
  - [ ] Update assertions for dual-table retrieval
  - [ ] Add tests for chunk-based responses
  - [ ] Verify citation format includes chunk metadata
  
- [ ] `tests/unit/test_retrieval.py`
  - [ ] Add `test_query_with_chunks()`
  - [ ] Add `test_chunk_deduplication()`
  - [ ] Add `test_ranking_algorithm()`

- [ ] `tests/unit/test_vectorstore.py`
  - [ ] Add `test_dual_table_query()`
  - [ ] Add `test_parallel_execution()`
  - [ ] Mock both sections and chunks tables

#### B. Run Full Test Suite
```bash
# Run all tests
pytest tests/ -v --cov=. --cov-report=term-missing

# Expected: 95%+ pass rate, 80%+ coverage
```

- [ ] Fix any failing tests
- [ ] Update test data if needed
- [ ] Add missing test cases for new features

**Exit Criteria**:
- ✅ All integration tests pass
- ✅ All unit tests pass
- ✅ Test coverage >80%
- ✅ No regressions in existing functionality

---

### Step 5: Frontend Connection (2-3h)

**Objective**: Validate end-to-end user flows

**Prerequisites**:
- Frontend running locally (port 3000)
- Backend running locally (port 8000)
- Test user account created

**Test Scenarios**:

#### A. Basic Chat Flow
- [ ] Open chat interface
- [ ] Send: "What is overtime pay?"
- [ ] Verify: Streaming response with 3+ citations
- [ ] Verify: Citations link to correct articles
- [ ] Verify: Response time <9s

#### B. Clarification Flow
- [ ] Send: "Tell me about leave"
- [ ] Verify: Clarification message appears
- [ ] Verify: 3-4 specific follow-up questions shown
- [ ] Click: "Maternity leave"
- [ ] Verify: Detailed answer with citations

#### C. Multi-turn Conversation
- [ ] Send: "What is the minimum wage?"
- [ ] Verify: Response received
- [ ] Send: "How often is it updated?"
- [ ] Verify: Context-aware answer (no clarification)
- [ ] Send: "What if I'm in Cebu?"
- [ ] Verify: Location-specific answer

#### D. Streaming UX
- [ ] Send any clear query
- [ ] Verify: First token appears <3.5s
- [ ] Verify: Smooth token-by-token streaming
- [ ] Verify: No UI flicker or layout shifts
- [ ] Verify: Citations appear after main text

#### E. Error Handling
- [ ] Send: "asdfghjkl" (gibberish)
- [ ] Verify: Polite error message
- [ ] Disconnect during streaming
- [ ] Verify: Backend handles gracefully (no crash)

**Exit Criteria**:
- ✅ All 5 test scenarios work end-to-end
- ✅ Streaming UX is smooth and responsive
- ✅ Citations display correctly in frontend
- ✅ Error handling is user-friendly
- ✅ No console errors or warnings

---

## 📊 Success Metrics (Updated)

## 📊 Success Metrics (Updated)

| Metric | Phase 1.E Baseline | Phase 1.0.5 Target | Status |
|--------|-------------------|-------------------|--------|
| Avg Latency (Clear) | 12.4s | <9s | ⏳ Pending Test |
| Avg Latency (Vague) | 12.4s | <1.5s | ⏳ Pending Test |
| Time-to-First-Token | N/A | <3.5s | ✅ 2.5-3.5s |
| Citations per Query | 1-3 | 5+ | ⏳ Pending Test |
| KB Coverage | 5 docs | 65+ chunks | ✅ Complete |
| Clarification Rate | 0% | 20-30% | ✅ Working |
| Cache Hit Rate | 0% | >30% | ✅ Implemented |
| Retrieval Accuracy | ~60% | 90%+ | ⏳ Pending Test |

---

## 📋 Quick Reference: Completed Work

<details>
<summary><b>Day 1: Query Analysis & Smart Retrieval</b> ✅</summary>

**What was built**:
- GPT-4o-mini query analysis with smart clarification detection
- Multi-strategy retrieval (keyword + semantic + direct article lookup)
- Context-aware follow-up handling (prevents false clarifications)
- Concept/article/keyword extraction from queries

**Key Files**:
- `services/pipeline/query_analysis.py`
- `adapters/vectorstore/supabase_store.py` (smart_retrieve method)
- `services/pipeline/retrieval.py`

**Tests**: All passing ✅

</details>

<details>
<summary><b>Day 2: Database Schema & Optimization</b> ✅</summary>

**What was built**:
- HNSW vector indexes (m=16, ef_construction=64)
- PostgreSQL connection pooling (ThreadedConnectionPool)
- Embedding LRU cache (reduces API calls)
- New schema: `labor_law_sources`, `labor_law_sections`, `labor_law_chunks`
- GIN indexes for full-text search

**Key Files**:
- `infra/supabase/schema.sql`
- `scripts/migrate_to_new_schema.py`
- `adapters/vectorstore/supabase_store.py` (connection pool)
- `adapters/embeddings/openai_embed.py` (LRU cache)

**Performance**: Vector search improved from 2-3s to <2s ✅

</details>

<details>
<summary><b>Day 3: Streaming & Grounding</b> ✅</summary>

**What was built**:
- Single-step rich-context grounding (GPT-4.1)
- Server-Sent Events (SSE) streaming endpoint
- Natural citation integration in responses
- Conversational tone with context awareness

**Key Files**:
- `services/pipeline/grounding.py` (generate_rich_context_prompt)
- `adapters/llm/openai_llm.py` (stream_generate method)
- `api/v1/routes_chat.py` (SSE endpoint)
- `services/chat_orchestrator.py` (early exit for vague queries)

**Performance**: Time-to-first-token 2.5-3.5s ✅

</details>

<details>
<summary><b>Day 4: KB Infrastructure & Ingestion</b> ✅</summary>

**What was built**:
- Incremental ingestion tracker (SHA-256 change detection)
- LLM-driven chunking (GPT-4o structure analysis)
- Source management system (10 sources populated)
- Chunk summarization (GPT-4.1, 500 max_tokens)
- Auto-chunking for large documents (>1000 words)

**Key Files**:
- `kb/ingest/incremental_tracker.py`
- `retrieval/llm_chunker.py`
- `kb/ingest/source_manager.py`
- `kb/ingest/sync_to_vectorstore.py`
- `scripts/populate_sources.py`

**Data Ingested**: PD-No-442 (65 sections + sub-chunks) ✅

</details>

---

## 🎯 Next Action

**Start with Step 1**: Update Retrieval Logic

```bash
# 1. Open the vectorstore adapter
code adapters/vectorstore/supabase_store.py

# 2. Add query_with_chunks() method (see detailed implementation above)

# 3. Update retrieval service
code services/pipeline/retrieval.py

# 4. Test locally
python -m pytest tests/unit/test_vectorstore.py -v
```

**Estimated Time**: 2-3 hours  
**Blockers**: None - all prerequisites complete ✅

---

## 📞 Need Help?

- **Retrieval not returning chunks?** Check HNSW index exists on both tables
- **Performance issues?** Verify connection pool and cache are enabled
- **Accuracy low?** Review ranking algorithm weights
- **Tests failing?** Check mock data includes both sections and chunks

---

**Last Updated**: November 20, 2025  
**Next Milestone**: Dual-table retrieval working (Step 1 complete)

