# PD-No-442 Chunking Strategy: Analysis & Recommendation

**Date**: November 14, 2025  
**Status**: ⏸️ Manual chunking PAUSED - Strategy revision required

---

## Executive Summary

After reviewing PD-No-442 chunking progress against our 200-800 word guidelines and ADR-002 architecture, **the current manual chunking approach must be revised**. The database schema (`schema_complete.sql`) already supports article-based storage, but we're not using it correctly.

---

## Key Findings

### 1. Guideline Violation

**Current chunks exceed size limits**:
- Chunk 00: 581 words ✅ (acceptable)
- Chunk 01: **3,662 words** ❌ (458% over 800-word maximum)
- Planned average: **2,744 words/chunk** ❌ (343% over maximum)

**Guideline**: 200-800 words per chunk

### 2. Implementation Status ✅

**GOOD NEWS**: Both schema and ingestion pipeline are **ALREADY IMPLEMENTED**:

**Database Schema** (`schema_complete.sql`):
- ✅ `labor_law_sources` table
- ✅ `labor_law_sections` table with full_text, summary, keywords, hierarchical metadata
- ✅ `labor_law_chunks` table for articles > 1000 words
- ✅ All indexes: GIN (full-text), B-tree (article_number), GIN (keywords)

**Ingestion Pipeline** (`kb/ingest/sync_to_vectorstore.py`):
- ✅ `ChunkSummarizer` with GPT-4o-mini for LLM summaries
- ✅ Keyword extraction (legal terms, articles, entities)
- ✅ Automatic embedding generation
- ✅ Upserts to `labor_law_sections` table with proper schema mapping

**Vector Store Adapter** (`adapters/vectorstore/supabase_store.py`):
- ✅ Maps to new schema: `full_text`, `summary`, `keywords`, `article_number`, etc.
- ✅ Extracts hierarchical metadata (book, title, chapter)
- ✅ Handles format flags (has_table, has_formula, has_list)

### 3. What's Working

The ingestion system **automatically**:
1. Generates LLM summaries via `ChunkSummarizer` (GPT-4o-mini)
2. Extracts legal keywords (Article refs, legal terms, entities)
3. Creates embeddings from chunk content
4. Stores in `labor_law_sections` with proper schema
5. Populates summary, keywords, and hierarchical fields

**Note on Embeddings**: Currently embeddings are generated from full article text. LLM summary embeddings are on hold - we'll use article embeddings for now.

**What `labor_law_chunks` is FOR**:
- Splitting **individual articles > 1000 words** into sub-chunks
- Each chunk links back to parent article via `section_id`
- Preserves article-level granularity

**What it's NOT for**:
- ❌ Grouping multiple articles into large chunks
- ❌ Manual section-based chunking

---

## PD-No-442 Document Profile

- **Total words**: 41,163
- **Total articles**: ~300 (Articles 7-302)
- **Average article**: ~137 words
- **Articles > 1000 words**: Estimated 5-10 only

**Conclusion**: Most articles are 50-200 words and should be stored individually in `labor_law_sections`, not grouped.

---

## Recommended Approach

### Manual Chunking (Article-by-Article)

Since the infrastructure is ready, we just need to **manually chunk PD-442** following the correct strategy:

**For each article** (target: 200-800 words per chunk):

1. **Create markdown files** in `kb/chunks/PD-No-442/`
   - One file per article or small group of related articles
   - Follow naming: `{number}-{article-range}-{topic}.md`
   - Include YAML frontmatter with metadata

2. **YAML frontmatter** (required):
```yaml
---
chunk_id: article-87-normal-working-hours
title: Article 87 - Normal Hours of Work
article_number: Article 87
semantic_type: statute
hierarchy:
  book: Book Three
  title: Conditions of Employment
  chapter: (if applicable)
keywords:
  - normal working hours
  - 8-hour work day
  - overtime
has_table: false
has_formula: false
has_list: true
---
```

3. **Ingestion** (automatic processing):
   - Run: `python -m kb.ingest.sync_to_vectorstore --manual --folder PD-No-442`
   - ChunkSummarizer automatically generates LLM summary
   - Keywords automatically extracted
   - Embedding automatically created from content
   - Data inserted into `labor_law_sections` table

**No custom scripts needed** - existing pipeline handles everything!

---

## Implementation Plan

### Manual Chunking Workflow

Since infrastructure is ready, we proceed with **manual chunking** using existing tools:

#### Step 1: Create Article Chunks (1-2 days)

**Process** ~300 articles from PD-442.txt:

1. **Read source**: `kb/docs/PD-No-442.txt`
2. **For each article or related group**:
   - Create `.md` file in `kb/chunks/PD-No-442/`
   - Add YAML frontmatter with metadata
   - Paste full article text
   - Target: 200-800 words per chunk
   - Group very short related articles if needed

**File naming**: `{number}-{topic}.md`
- Example: `07-book3-normal-working-hours.md`
- Example: `08-book3-overtime-premium-holiday-pay.md`

**Frontmatter template**:
```yaml
---
chunk_id: unique-identifier
title: Article X - Title
article_number: Article X
semantic_type: statute
hierarchy:
  book: Book Three
  title: Conditions of Employment
  chapter: Chapter I
keywords:
  - keyword1
  - keyword2
has_table: false
has_formula: false
has_list: true
---
```

#### Step 2: Ingest Chunks (0.5 day)

**Single command**:
```bash
python -m kb.ingest.sync_to_vectorstore --manual --folder PD-No-442
```

**Automatic processing**:
- ✅ ChunkSummarizer generates LLM summaries (GPT-4o-mini)
- ✅ Keywords extracted from content
- ✅ Embeddings generated from article text
- ✅ Data inserted into `labor_law_sections` table
- ✅ Hierarchical metadata populated

**Cost**: ~$0.02 for 300 summaries

#### Step 3: Validate (0.5 day)

```bash
# Dry run first
python -m kb.ingest.sync_to_vectorstore --manual --folder PD-No-442 --dry-run

# Check results in database
# Verify ~300 articles in labor_law_sections table
```

---

## Multi-Strategy Retrieval Support

Once articles are in `labor_law_sections`, we can implement ADR-002 multi-strategy retrieval:

### Strategy 1: Keyword Search (Fast, High Precision)
```sql
-- Use existing GIN index
SELECT * FROM labor_law_sections
WHERE to_tsvector('english', full_text) @@ plainto_tsquery('english', $keywords);
```

### Strategy 2: Semantic Search (Nuanced, Conceptual)
```sql
-- Use HNSW vector index on summaries
SELECT * FROM labor_law_sections
WHERE 1 - (embedding <=> $query_embedding) > 0.3
ORDER BY embedding <=> $query_embedding;
```

### Strategy 3: Direct Article Lookup (Instant)
```sql
-- Use B-tree index on article_number
SELECT * FROM labor_law_sections
WHERE article_number = 'Article 87';
```

---

## Timeline & Cost

| Task | Duration | Cost |
|------|----------|------|
| Manual article chunking | 1-2 days | $0 |
| Ingestion (automated) | 0.5 day | ~$0.02 |
| Validation | 0.5 day | $0 |
| **Total** | **2-3 days** | **~$0.02** |

**Notes**:
- LLM summaries auto-generated during ingestion (GPT-4o-mini)
- Keywords auto-extracted during ingestion
- Embeddings generated from article text (summary embeddings on hold)
- All processing automated via existing pipeline

---

## Immediate Actions

### ✅ CONFIRMED READY
- Database schema implemented (`schema_complete.sql`)
- Ingestion pipeline with ChunkSummarizer ready
- Vector store adapter configured for new schema
- LLM summary & keyword extraction working

### ⏳ TODO - Manual Chunking
1. **Start chunking** PD-442 articles into markdown files
2. Follow 200-800 word guideline per chunk
3. Include complete YAML frontmatter
4. Group very short related articles if needed
5. Create ~50-100 chunk files (not 15 large chunks)

### 🚀 READY TO PROCEED
**Command to start**:
```bash
# Test with first chunk
python -m kb.ingest.sync_to_vectorstore --manual --file kb/chunks/PD-No-442/02-article-12-objectives.md --dry-run

# When ready, ingest all
python -m kb.ingest.sync_to_vectorstore --manual --folder PD-No-442
```

---

## Benefits

✅ **Aligns with ADR-002 architecture** (already implemented in DB)  
✅ **Enables multi-strategy retrieval** (keyword + semantic + direct lookup)  
✅ **Precise citations** (article-level, not chunk-level)  
✅ **Hierarchical navigation** (Book → Title → Article)  
✅ **Easier maintenance** (update individual articles)  
✅ **Better search performance** (optimized indexes)  

---

## References

- **Database Schema**: `infra/supabase/schema_complete.sql` (Phase 1.0.5 - IMPLEMENTED)
- **Architecture Design**: `docs/adr/002-rag-pipeline-limitations-and-future-architecture.md`
- **Chunking Guidelines**: `docs/database_ingestion/QUICK_REFERENCE.md`
- **Current Progress**: `kb/chunks/PD-No-442/CHUNKING_PROGRESS.md`

---

## Conclusion

**Infrastructure is ready. We just need to chunk properly.**

The database schema, ingestion pipeline, LLM summarization, and keyword extraction are all implemented and working. What we need:

1. **Manual chunking** following 200-800 word guideline
2. **~50-100 markdown files** (not 15 large chunks)
3. **Proper YAML frontmatter** for each chunk
4. **Run existing ingestion command**

The system will automatically:
- Generate LLM summaries (GPT-4o-mini)
- Extract legal keywords
- Create embeddings from article text
- Populate `labor_law_sections` table
- Enable multi-strategy retrieval

**Next step**: Start manual chunking of PD-442 articles (2-3 days, ~$0.02 cost).

---

## Important Notes

### Embedding Strategy
**Current**: Embeddings generated from full article text  
**On Hold**: Embedding summaries instead of full text  
**Reason**: Simplify initial implementation, can optimize later

### Architecture Alignment
This approach:
- ✅ Follows 200-800 word guideline
- ✅ Uses existing `labor_law_sections` table
- ✅ Leverages implemented ChunkSummarizer
- ✅ Enables multi-strategy retrieval (keyword + semantic + direct)
- ✅ Provides article-level citations
