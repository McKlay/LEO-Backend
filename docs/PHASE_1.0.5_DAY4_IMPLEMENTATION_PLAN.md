# Phase 1.0.5 Day 4: KB Enhancement Implementation Plan

**Date**: November 13, 2025  
**Status**: 3/5 Components Complete - Missing Summarizer Before Integration  
**Duration**: 5-7 hours (includes LLM chunking implementation)

---

## ⚠️ Current Status: Missing Critical Component

**Completed** (3/5):
- ✅ Schema Enhancement (ingestion_history, format flags)
- ✅ Incremental Ingestion Tracker (7/7 tests passing)
- ✅ LLM-Driven Chunker (443 lines, regex fallback working)

**Missing** (2/5):
- ⏳ **Chunk Summarizer (BLOCKING)** - GPT-4o-mini summary + keyword extraction
- ⏳ Integration & Testing - sync_to_vectorstore.py updates

**See [DAY4_MISSING_COMPONENTS.md](./DAY4_MISSING_COMPONENTS.md) for detailed gap analysis and implementation specs.**

---

## Executive Summary

**Enhanced Approach**: LLM-driven intelligent chunking with incremental ingestion tracking

### Core Improvements

1. **Incremental Ingestion** - Track processed files with content hashes; only ingest new/modified files
2. **LLM-Driven Chunking** - Use GPT-4o (or gpt-4.1) to intelligently analyze document structure and create semantically optimal chunks
3. **Format Preservation** - LLM identifies and preserves critical data formats (tables, equations, lists, code blocks)
4. **Smart Summarization** - GPT-4o-mini generates summaries with legal keyword extraction
5. **Token Optimization** - Process documents incrementally to stay within daily free tier limits

### Model Selection Strategy

**For Chunking**: **GPT-4o** (250K tokens/day free tier)
- Superior structural understanding for legal documents
- Better at identifying semantic boundaries (Articles, Sections, sub-provisions)
- Can handle complex formats (tables, equations, nested lists)
- Preserves critical data integrity
- Fallback: gpt-4.1 (same tier)

**For Summarization**: **GPT-4o-mini** (2.5M tokens/day free tier)
- Sufficient for concise legal summaries
- 10x more daily tokens = can process all documents
- Fast response time
- Cost-effective for repetitive task

**Token Budget Estimation**:
- PD-442 (2061 lines): ~15K tokens for chunking analysis
- All 10 docs chunking: ~60K tokens (within 250K/day)
- Summarization (150-300 chunks @ 500 tokens each): ~150K tokens (within 2.5M/day)

---

## Implementation Overview

**See [ENHANCED_LLM_CHUNKING.md](./ENHANCED_LLM_CHUNKING.md) for complete technical details.**

This document provides a high-level implementation timeline. The enhanced approach includes:

1. **Incremental Ingestion System** - Track files with SHA-256 hashes, only process new/modified
2. **LLM-Driven Chunking** - GPT-4o analyzes document structure intelligently
3. **Format Preservation** - Tables, formulas, lists kept intact
4. **Smart Summarization** - GPT-4o-mini generates summaries + keywords
5. **Token Optimization** - Process 1-2 docs/day to stay within free tier

---

## Quick Start

### Prerequisites
```powershell
# Ensure virtual environment activated
.venv\Scripts\Activate.ps1

# Run schema migration (adds ingestion_history table)
python scripts/migrate_to_new_schema.py
```

### Daily Incremental Ingestion

**Day 1** (Critical docs - ~50K tokens):
```powershell
python -m kb.ingest.sync_to_vectorstore --file PD-No-442.txt
python -m kb.ingest.sync_to_vectorstore --file PD-No-851.txt
```

**Day 2** (High priority - ~40K tokens):
```powershell
python -m kb.ingest.sync_to_vectorstore --file DOLE-Handbook.txt
python -m kb.ingest.sync_to_vectorstore --file RA-No-11058.txt
```

**Day 3** (Remaining - ~30K tokens):
```powershell
python -m kb.ingest.sync_to_vectorstore --file RA-No-11199.txt
python -m kb.ingest.sync_to_vectorstore --file RA-No-10361.txt
python -m kb.ingest.sync_to_vectorstore --file SEnA.txt
```

**Day 4** (Final batch):
```powershell
python -m kb.ingest.sync_to_vectorstore --file NLRC-Rules.txt
python -m kb.ingest.sync_to_vectorstore --file DOLE-Dep-Order-147-15.txt
python -m kb.ingest.sync_to_vectorstore --file DOLE-Covid-Protocols.txt
```

### Future: Adding New Documents

```powershell
# 1. Copy new .txt file to kb/docs/
# 2. Add metadata to DOCUMENT_REGISTRY in sync_to_vectorstore.py
# 3. Run ingestion
python -m kb.ingest.sync_to_vectorstore --file NEW-DOC.txt

# Or auto-detect new files:
python -m kb.ingest.sync_to_vectorstore --new-only
```

---

## Implementation Tasks

### Day 4 Morning: Infrastructure (2-3 hours)

- [ ] **Schema Enhancement** (20 min)
  - [ ] Run migration script to add `ingestion_history` table
  - [ ] Add format flags to `labor_law_sections` (has_table, has_formula, has_list)
  - [ ] Verify indexes created

- [ ] **Implement Incremental Tracker** (45 min)
  - [ ] Create `kb/ingest/incremental_tracker.py`
  - [ ] Add `IngestionTracker` class with SHA-256 hashing
  - [ ] Implement `should_ingest()`, `record_ingestion()`, `delete_old_chunks()`
  - [ ] Add database queries for tracking

- [ ] **Implement LLM Chunker** (90 min)
  - [ ] Create `retrieval/llm_chunker.py`
  - [ ] Add `LLMDrivenChunker` class with GPT-4o integration
  - [ ] Implement structure analysis prompt
  - [ ] Add large document handling (sliding window)
  - [ ] Implement format detection (tables, formulas, lists)
  - [ ] Add fallback to regex chunking on errors

### Day 4 Afternoon: Integration (2-3 hours)

- [ ] **Update Ingestion Pipeline** (60 min)
  - [ ] Modify `kb/ingest/sync_to_vectorstore.py`
  - [ ] Integrate `IngestionTracker`
  - [ ] Switch to `LLMDrivenChunker`
  - [ ] Add summary + keyword generation with GPT-4o-mini
  - [ ] Update CLI with `--force`, `--use-regex`, `--new-only` flags

- [ ] **Testing** (45 min)
  - [ ] Test incremental ingestion (ingest, modify, re-ingest)
  - [ ] Test LLM chunking with sample doc (PD-851 small test)
  - [ ] Verify table/formula preservation
  - [ ] Check ingestion_history tracking
  - [ ] Validate summaries and keywords

- [ ] **First Production Ingest** (30 min)
  - [ ] Ingest PD-No-851.txt (small, critical, good test case)
  - [ ] Validate chunks in database
  - [ ] Check embeddings generated
  - [ ] Verify summaries and keywords
  - [ ] Test retrieval with sample queries

---

## Daily Ingestion Schedule (Days 5-8)

### Day 5: Critical Documents
- [ ] **Morning**: PD-No-442.txt (Labor Code - largest, ~15K tokens)
- [ ] **Afternoon**: PD-No-851.txt (already done if tested on Day 4)
- [ ] **Token usage**: ~23K / 250K (9%)

### Day 6: High Priority
- [ ] **Morning**: DOLE-Handbook.txt (~18K tokens)
- [ ] **Afternoon**: RA-No-11058.txt (OSH Law, ~5K tokens)
- [ ] **Token usage**: ~23K / 250K (9%)

### Day 7: Medium Priority
- [ ] **Morning**: RA-No-11199.txt (SSS Act, ~7K tokens)
- [ ] RA-No-10361.txt (Domestic Workers, ~6K tokens)
- [ ] **Afternoon**: SEnA.txt (Rules, ~4K tokens)
- [ ] **Token usage**: ~17K / 250K (7%)

### Day 8: Remaining
- [ ] NLRC-Rules.txt (~5K tokens)
- [ ] DOLE-Dep-Order-147-15.txt (~4K tokens)
- [ ] DOLE-Covid-Protocols.txt (~3K tokens)
- [ ] **Token usage**: ~12K / 250K (5%)

**Total Estimated Tokens**: ~75K (well within 250K/day limit)

---

## Validation Checklist

After each ingestion:

- [ ] **Database Check**:
  ```sql
  -- Check chunk count
  SELECT COUNT(*) FROM labor_law_sections WHERE source_id IN (
      SELECT id FROM labor_law_sources WHERE reference LIKE '%[doc-name]%'
  );
  
  -- Verify format flags
  SELECT has_table, has_formula, has_list, COUNT(*)
  FROM labor_law_sections
  GROUP BY has_table, has_formula, has_list;
  
  -- Check ingestion history
  SELECT * FROM ingestion_history ORDER BY created_at DESC LIMIT 5;
  ```

- [ ] **Quality Spot Check** (manual review of 3-5 chunks):
  - [ ] Tables intact and readable
  - [ ] Formulas not split
  - [ ] Lists complete
  - [ ] Summaries accurate and concise
  - [ ] Keywords relevant

- [ ] **Retrieval Test**:
  ```python
  # Test with sample query related to ingested doc
  # e.g., "What is 13th month pay?" after PD-851 ingestion
  ```

---

## Troubleshooting

### Issue: LLM returns invalid JSON
**Solution**: Automatic fallback to regex chunking is implemented

### Issue: Token limit exceeded
**Solution**: Large document handler automatically splits by Books/Titles

### Issue: File already ingested error
**Solution**: Use `--force` flag to override
```powershell
python -m kb.ingest.sync_to_vectorstore --file PD-No-442.txt --force
```

### Issue: Want to use regex chunking (faster, cheaper)
**Solution**: Use `--use-regex` flag
```powershell
python -m kb.ingest.sync_to_vectorstore --file SMALL-DOC.txt --use-regex
```

---

## Success Criteria

### Day 4 (Infrastructure)
- ✅ `ingestion_history` table created
- ✅ `LLMDrivenChunker` implemented
- ✅ `IngestionTracker` functional
- ✅ First test document ingested successfully
- ✅ Incremental ingestion working (skip unchanged files)

### Day 8 (All Documents Ingested)
- ✅ All 10 documents in database (150-300 chunks)
- ✅ Tables/formulas preserved (spot check 10 samples)
- ✅ Summaries generated for all chunks >50 words
- ✅ Keywords extracted (avg 5-8 per chunk)
- ✅ Ingestion history tracking all files
- ✅ Token usage within daily limits

---

## Performance Targets

| Metric | Target | How to Measure |
|--------|--------|----------------|
| LLM chunking quality | >90% preserved formats | Manual review of 20 chunks |
| Incremental detection | 100% skip unchanged | Re-run ingestion, check logs |
| Token efficiency | <100K total for all docs | Sum from ingestion_history |
| Chunk semantic coherence | >85% complete provisions | Review 20 random chunks |
| Summary quality | >80% accurate | Manual review of 20 summaries |
| Keyword relevance | >75% useful for search | Test 10 queries |

---
| RA-No-11058.txt | Statute (OSH) | Medium | ⭐⭐ High |
| RA-No-11199.txt | Statute (SSS) | Medium | ⭐⭐ High |
| RA-No-10361.txt | Statute (Domestic Workers) | Medium | ⭐⭐ High |
| DOLE-Handbook.txt | Handbook/Guide | 2705 lines | ⭐⭐⭐ Critical |
| DOLE-Dep-Order-147-15.txt | Dept Order | Medium | ⭐ Medium |
| SEnA.txt | Procedural Rules | Medium | ⭐ Medium |
| NLRC-Rules.txt | Procedural Rules | Medium | ⭐ Medium |
| DOLE-Covid-Protocols.txt | Guidelines | Small | ⭐ Low |

**Expected Output**: 150-300 chunks covering comprehensive labor law topics

---

## Document Structure Analysis

### 1. Statutes (PD-442, RA-*, PD-851)
**Structure**:
```
BOOK → TITLE → CHAPTER → Article XXX (with sections)
```

**Chunking Strategy**:
- **Primary**: Article-level chunks (e.g., "Article 123: Termination by employer")
- **Fallback**: If article >300 words, split by sections with 20-word overlap
- **Metadata**: `book`, `title_name`, `chapter`, `article_number`, `article_title`

**Example from PD-442**:
```
Article 13. Definitions.
(a) "Workers" means any member of the labor force...
(b) "Recruitment and placement" refers to...
```
→ Single chunk if <300 words, or split into sub-chunks

### 2. Handbooks (DOLE-Handbook.txt)
**Structure**:
```
Section 1. MINIMUM WAGE
  A. COVERAGE
  B. MINIMUM WAGE RATES
  C. RULES IN DETERMINING...
```

**Chunking Strategy**:
- **Primary**: Section-level (e.g., "1. MINIMUM WAGE")
- **Secondary**: Subsection (A, B, C) if section >300 words
- **Metadata**: `section`, `subsection`, `topic`

### 3. Procedural Rules (SEnA, NLRC-Rules)
**Structure**:
```
RULE I
RULE II
  Section 1.
  Section 2.
```

**Chunking Strategy**:
- **Primary**: Rule-level
- **Secondary**: Section-level within rules
- **Metadata**: `rule`, `section`

---

## Implementation Steps

### Step 1: Schema Migration (15 mins)

**Action**: Run migration script
```powershell
python scripts/migrate_to_new_schema.py
```

**Verification**:
```sql
-- Check tables created
SELECT table_name FROM information_schema.tables 
WHERE table_name IN ('labor_law_sources', 'labor_law_sections', 'labor_law_chunks');

-- Check indexes
SELECT indexname, indexdef FROM pg_indexes 
WHERE tablename = 'labor_law_sections';

-- Should see:
-- - idx_sections_fts (GIN for full-text)
-- - idx_sections_embedding_hnsw (HNSW for vectors)
-- - idx_sections_article (B-tree)
-- - idx_sections_source (B-tree)
```

**Output**: New schema ready, old table preserved

---

### Step 2: Enhancement - Add Summary Generation (30 mins)

**Current Gap**: `sync_to_vectorstore.py` doesn't generate summaries

**Enhancement Required**:

1. **Add LLM adapter to ingester**:
```python
from adapters.llm.openai_llm import OpenAILLMAdapter

class KnowledgeBaseIngester:
    def __init__(self, embeddings_adapter, vectorstore_adapter, llm_adapter=None):
        self.embeddings = embeddings_adapter
        self.vectorstore = vectorstore_adapter
        self.llm = llm_adapter or OpenAILLMAdapter(model="gpt-4o-mini")
        # ... rest
```

2. **Add summarization method**:
```python
async def _generate_summary(self, content: str, doc_type: str) -> str:
    """Generate concise summary for semantic search."""
    if len(content.split()) < 50:
        return content  # Too short, use as-is
    
    prompt = f"""Summarize this Philippine labor law {doc_type} in 2-3 sentences.
Focus on key legal provisions and worker rights/obligations.

Content:
{content[:1000]}  # Limit for token efficiency

Summary:"""
    
    response = await self.llm.generate(
        prompt=prompt,
        max_tokens=150,
        temperature=0.3
    )
    
    return response.content.strip()
```

3. **Integrate into chunking flow**:
```python
# In ingest_file() method, after chunking:
for chunk in chunks:
    # Generate summary for chunks >100 words
    if chunk.word_count >= 100:
        summary = await self._generate_summary(chunk.content, metadata["doc_type"])
        chunk.metadata["summary"] = summary
```

**Why This Matters**:
- Summaries improve semantic search quality
- Reduces noise from long legal text
- Enables hybrid search: query matches summary, return full text

---

### Step 3: Automated Bulk Ingestion (60-90 mins)

**Action**: Run ingestion for all documents
```powershell
# Activate virtual environment
.venv\Scripts\Activate.ps1

# Dry run first to verify
python -m kb.ingest.sync_to_vectorstore --all --dry-run

# Actual ingestion
python -m kb.ingest.sync_to_vectorstore --all
```

**Monitoring**:
```
Expected output:
====================================
Processing file: PD-No-442.txt
Chunked document 'Presidential Decree No. 442': 85 chunks created (avg 245 words/chunk)
Generating embeddings for 85 chunks...
Upserting 85 documents to vector store...
✓ Successfully ingested PD-No-442.txt: 85 chunks, 12,450 tokens

Processing file: PD-No-851.txt
...

====================================
Ingestion Summary:
  Files processed: 10/10
  Total chunks: 187
  Total tokens: 45,320
  Failed: 0
====================================
```

**Troubleshooting**:
- **Timeout errors**: Increase batch size in `embed_batch()` or add retry logic
- **Memory errors**: Process files sequentially with smaller batches
- **Encoding errors**: TextLoader has fallback to `latin-1`

---

### Step 4: Ingestion Validation (15 mins)

**Database Checks**:
```sql
-- Count sections ingested
SELECT COUNT(*) FROM labor_law_sections;
-- Expected: 150-300

-- Check sources
SELECT source_type, COUNT(*) as count 
FROM labor_law_sources 
GROUP BY source_type;
-- Expected: statute (5), handbook (1), procedural_rules (2), etc.

-- Sample records
SELECT article_number, article_title, 
       LEFT(full_text, 100) as preview,
       array_length(keywords, 1) as keyword_count
FROM labor_law_sections
LIMIT 5;

-- Check embeddings
SELECT COUNT(*) FROM labor_law_sections WHERE embedding IS NOT NULL;
-- Should match total count

-- Verify summaries generated
SELECT COUNT(*) FROM labor_law_sections WHERE summary IS NOT NULL;
-- Should be >0 if enhancement added
```

**Quality Checks**:
- [ ] All 10 documents processed
- [ ] No duplicate chunks (check by `id`)
- [ ] Metadata populated (source, doc_type, article_number)
- [ ] URLs accessible
- [ ] Embeddings generated

---

### Step 5: Retrieval Testing (30 mins)

**Direct Article Lookup**:
```python
# Test: "What is Article 13 about?"
# Should find: Article 13 definitions from Labor Code
```

**Keyword Search**:
```python
# Test: "13th month pay calculation"
# Should find: PD-851 + DOLE Handbook sections
```

**Semantic Search**:
```python
# Test: "What are my rights if I'm terminated?"
# Should find: Articles 293-299 (termination), separation pay sections
```

**Broad Queries**:
```python
# Test: "employee benefits"
# Should return: 5+ chunks (13th month, leave, SSS, retirement, etc.)
```

---

### Step 6: Performance Benchmarking (45 mins)

**Test Suite** (20 diverse queries):

| Category | Query | Expected Sources | Target Latency |
|----------|-------|------------------|----------------|
| Clear | "What is 13th month pay?" | PD-851, Handbook | <9s |
| Clear | "How many leave days?" | Handbook (SIL) | <9s |
| Vague | "My rights?" | Clarification | <1.5s |
| Vague | "Can they fire me?" | Clarification | <1.5s |
| Follow-up | "How is it calculated?" (after 13th month) | PD-851 | <9s |
| Broad | "Employee benefits overview" | 5+ sources | <12s |
| Specific | "Article 293 termination" | Labor Code Art 293 | <6s |

**Metrics to Capture**:
```python
import time
from collections import defaultdict

results = defaultdict(list)

for query in test_queries:
    start = time.time()
    response = await chat_orchestrator.process(query)
    latency = time.time() - start
    
    results['latencies'].append(latency)
    results['chunk_counts'].append(len(response.citations))
    results['clarifications'].append(response.needs_clarification)
    results['confidence'].append(response.confidence)

# Calculate metrics
avg_latency = sum(results['latencies']) / len(results['latencies'])
clarification_rate = sum(results['clarifications']) / len(results['clarifications'])
avg_chunks = sum(results['chunk_counts']) / len(results['chunk_counts'])
```

**Target Metrics**:
- ✅ Clear queries: avg <9s
- ✅ Vague queries: avg <1.5s
- ✅ Clarification rate: 20-30% (first queries)
- ✅ Citations per query: 3-5 (clear), 0 (vague)
- ✅ Confidence: >0.6 (clear), N/A (vague)

---

### Step 7: Quality Assurance (30 mins)

**Manual Review Checklist** (10 responses):

**Response Quality**:
- [ ] Tone: Conversational and empathetic?
- [ ] Citations: Naturally integrated, not robotic?
- [ ] Accuracy: Claims match source text?
- [ ] Completeness: Answers the question fully?
- [ ] Actionability: Provides next steps?

**Clarification Quality** (5 clarification responses):
- [ ] Questions are specific, not generic ("Can you clarify?" ❌)
- [ ] 3-4 follow-up questions provided
- [ ] Suggested topics relevant to user intent
- [ ] User can pick a path to continue conversation

**Citation Format**:
```
✅ Good: "Under Article 123 of the Labor Code, employers must..."
❌ Bad: "According to source_id_xyz123..."
```

---

## Edge Cases to Test

1. **Out-of-scope query**: "How do I bake a cake?"
   - Expected: Polite refusal, suggest labor law topics

2. **Very vague query**: "Help me"
   - Expected: Clarification with labor law topic suggestions

3. **Multi-article reference**: "What are all termination rules?"
   - Expected: 5+ citations from Articles 293-299

4. **Streaming interruption**: Disconnect mid-response
   - Expected: Graceful handling, no crashes

5. **Follow-up after clarification**: 
   - User: "My rights?" → Clarification
   - User: "Termination" → Full answer
   - Expected: Context maintained, proper response

---

## Success Criteria

### Must Have ✅
- [ ] Schema migration completed
- [ ] All 10 documents ingested (150-300 chunks)
- [ ] Embeddings generated for all chunks
- [ ] HNSW index created and performant
- [ ] Multi-strategy retrieval working (direct, keyword, semantic)
- [ ] Performance targets met:
  - Clear queries: <9s avg
  - Vague queries: <1.5s avg
  - Clarification rate: 20-30%
- [ ] Quality review passed (10 responses)
- [ ] All integration tests passing

### Nice to Have 🎯
- [ ] Summary generation implemented and working
- [ ] Cache hit rate >30%
- [ ] Zero failed ingestions
- [ ] Comprehensive performance report generated
- [ ] Edge cases handled gracefully

---

## Rollback Plan

**If critical issues arise**:

1. **Database**: Old `labor_law_embeddings` table still exists
   ```sql
   -- Revert to old table
   DROP TABLE labor_law_sections CASCADE;
   DROP TABLE labor_law_sources CASCADE;
   -- Update code to use labor_law_embeddings
   ```

2. **Ingestion failures**: Re-run individual files
   ```powershell
   python -m kb.ingest.sync_to_vectorstore --file kb/docs/PD-No-442.txt
   ```

3. **Performance regression**: Disable new features via flags
   ```python
   ENABLE_SMART_CLARIFICATION = False
   ENABLE_MULTI_STRATEGY_RETRIEVAL = False
   ```

---

## Timeline

| Time | Task | Duration |
|------|------|----------|
| 0:00 | Schema migration | 15 min |
| 0:15 | Add summary generation code | 30 min |
| 0:45 | Bulk ingestion (10 docs) | 90 min |
| 2:15 | Ingestion validation | 15 min |
| 2:30 | Break | 15 min |
| 2:45 | Retrieval testing | 30 min |
| 3:15 | Performance benchmarking | 45 min |
| 4:00 | Quality assurance | 30 min |
| 4:30 | Documentation & wrap-up | 30 min |
| **5:00** | **DONE** | **5 hours** |

---

## Next Steps After Day 4

Once Day 4 is complete, Phase 1.0.5 is **production-ready** for:
- Multi-turn conversations
- Smart clarification
- Citation-driven responses
- Streaming UX
- Comprehensive labor law coverage

**Phase 1.1 Preview**: Conversation Management API
- Persistent conversation history
- User session management
- Multi-device conversation sync
- Conversation analytics

---

**Last Updated**: November 13, 2025  
**Author**: GitHub Copilot  
**Status**: Ready for execution
