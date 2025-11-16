# Metadata Alignment Investigation Report

**Date**: November 16, 2025  
**Investigation Type**: Schema, Pipeline Architecture, and Implementation Alignment  
**Status**: ⚠️ CRITICAL MISALIGNMENTS IDENTIFIED

---

## Executive Summary

Investigation reveals **critical inconsistencies** between:
1. ADR-002 pipeline architecture goals
2. Database schema implementation (`schema_complete.sql`)
3. Manual chunk metadata formats (`metadata.json` and YAML frontmatter)
4. Loader/validator implementations

**Key Finding**: The current implementation does NOT fully support the smart multi-strategy retrieval architecture outlined in ADR-002.

---

## 1. RAG Architecture Discussion - Smart Multi-Strategy Retrieval

### ADR-002 Architecture Goals

From `docs/adr/002-rag-pipeline-limitations-and-future-architecture.md`:

**Stage 2: Smart Parallel Multi-Strategy Retrieval**

#### Strategy 1: Full-Text Keyword Search
- **Uses**: PostgreSQL GIN index on `full_text` + `article_title`
- **Target Speed**: 0.6-0.8s
- **Index Required**: `GIN(to_tsvector('english', full_text || ' ' || article_title))`

#### Strategy 2: Semantic Vector Search  
- **Uses**: HNSW index on embeddings (from **summaries**, not full text)
- **Target Speed**: 1.8-2.0s (down from 3-4s)
- **Critical Detail**: "Search on **summaries** not full text (better semantic representation)"
- **Index Required**: `HNSW (embedding vector_cosine_ops)`

#### Strategy 3: Direct Article/Law Lookup
- **Uses**: B-tree index on `article_number` and `source_reference`
- **Target Speed**: 0.1-0.2s (ultra-fast)
- **Index Required**: B-tree on `article_number`

### Database Schema Requirements (from ADR-002)

```sql
CREATE TABLE labor_law_sections (
    id UUID PRIMARY KEY,
    source_id UUID REFERENCES labor_law_sources(id),
    
    -- Hierarchical metadata
    book_number INT,
    title_number INT,
    chapter_number INT,
    section_number INT,
    article_number TEXT,
    article_title TEXT,
    
    -- Content
    full_text TEXT,           -- FULL article text (not chunked)
    summary TEXT,             -- LLM-generated summary for semantic search
    keywords TEXT[],          -- Extracted key terms
    
    -- Vector embedding (of summary, not full text)
    embedding vector(1536),
    
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);
```

**Key Architecture Decision**: 
> "Summary Embeddings: Semantic search on LLM-generated summaries (better semantic representation than raw legal text)"

---

## 2. Current Implementation Analysis

### 2.1 Database Schema (`schema_complete.sql`)

**✅ CORRECT - Aligned with ADR-002**:

```sql
CREATE TABLE IF NOT EXISTS labor_law_sections (
    id UUID PRIMARY KEY,
    source_id UUID REFERENCES labor_law_sources(id),
    article_number VARCHAR(50),
    article_title TEXT,
    full_text TEXT NOT NULL,
    summary TEXT,  -- ✅ LLM-generated summary column exists
    keywords TEXT[],  -- ✅ Array column exists
    metadata JSONB,
    
    -- Hierarchical structure
    book VARCHAR(100),  -- ❌ TEXT instead of INT
    title_name VARCHAR(200),  -- ❌ Different name: should be title_number INT
    chapter VARCHAR(100),  -- ❌ TEXT instead of INT
    
    -- Format flags
    has_table BOOLEAN,
    has_formula BOOLEAN,
    has_list BOOLEAN,
    
    -- Vector embedding
    embedding vector(1536),  -- ⚠️ UNCLEAR: Is this from summary or full_text?
    
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);
```

**Indexes Created**:
```sql
-- ✅ Strategy 1: Full-text search index
CREATE INDEX idx_sections_fts 
ON labor_law_sections 
USING GIN(to_tsvector('english', full_text || ' ' || COALESCE(article_title, '')));

-- ✅ Strategy 3: Direct lookup index
CREATE INDEX idx_sections_article 
ON labor_law_sections(article_number);

-- ✅ Keyword search support
CREATE INDEX idx_sections_keywords
ON labor_law_sections USING GIN (keywords);

-- ⚠️ Strategy 2: Vector search index - NOT IN schema_complete.sql!
-- ADR-002 specifies: "See: infra/supabase/create_hnsw_indexes.sql"
-- This file may not exist yet
```

### 2.2 Schema Issues Identified

| ADR-002 Specification | Actual Schema | Issue |
|----------------------|---------------|-------|
| `book_number INT` | `book VARCHAR(100)` | ❌ Type mismatch - should be INT for numeric sorting |
| `title_number INT` | `title_name VARCHAR(200)` | ❌ Wrong field name AND type |
| `chapter_number INT` | `chapter VARCHAR(100)` | ❌ Type mismatch |
| `section_number INT` | ❌ **MISSING** | ❌ Not implemented |
| `source_reference` for direct lookup | ❌ **MISSING** | ❌ Can't do fast law lookup (e.g., "PD 851") |
| HNSW index on embedding | ⚠️ **External file** | ⚠️ Not in main schema, unclear if deployed |

**Critical Question**: 
- **What does `embedding` column contain?**
  - ADR-002: Should be embedding of **summary** (not full_text)
  - Current code: Unknown - need to check ingestion pipeline

---

## 3. Metadata Formats Analysis

### 3.1 Manual Chunk `metadata.json`

**Current Format** (PD-No-442, PD-No-851):
```json
{
  "source": "Presidential Decree No. 851",
  "reference": "PD 851",
  "short_name": "13th Month Pay Law",
  "doc_type": "statute",
  "year": "1975",
  "url": "https://lawphil.net/statutes/presdecs/pd1975/pd_851_1975.html",
  "total_chunks": 5,
  "chunking_strategy": "manual",
  "last_updated": "2024-11-13",
  "notes": "..."
}
```

**Issues**:
1. ❌ **NOT stored in database** - only used during ingestion
2. ❌ No mapping to `labor_law_sources` table fields
3. ❌ `reference` field exists BUT not stored in `labor_law_sections`
4. ✅ Maps to ingestion tracker and source manager

### 3.2 Chunk File YAML Frontmatter

**Current Format** (PD-No-851/01-decree-main.md):
```yaml
---
chunk_id: pd851_decree_main
title: Presidential Decree No. 851 - Main Decree (Sections 1-3)
article_number: pd851_decree_sec1_3
semantic_type: decree
hierarchy:
  part: Main Presidential Decree  # ❌ NOT in schema
  sections: Preamble and Sections 1-3  # ❌ NOT in schema
keywords:
  - 13th month pay
  - basic salary
has_table: false
has_formula: false
has_list: false
---
```

**Critical Issues**:

| YAML Field | DB Column | Status |
|------------|-----------|--------|
| `chunk_id` | Not stored | ❌ Lost during ingestion |
| `title` | `article_title` | ✅ Mapped correctly |
| `article_number` | `article_number` | ✅ Mapped correctly |
| `semantic_type` | Not stored | ❌ Lost (stored in metadata JSONB only) |
| `hierarchy.part` | ❌ No column | ❌ Not in schema |
| `hierarchy.sections` | ❌ No column | ❌ Not in schema |
| `hierarchy.book` | `book` | ⚠️ Schema uses VARCHAR, expects "Book One" not INT |
| `hierarchy.title` | `title_name` | ⚠️ Wrong name in schema |
| `hierarchy.chapter` | `chapter` | ⚠️ Schema uses VARCHAR, expects "Chapter 1" not INT |
| `keywords` | `keywords[]` | ✅ Mapped correctly |
| `has_table/formula/list` | Respective columns | ✅ Mapped correctly |

**PD-No-442 Example** (00-preliminary-title-preamble.md):
```yaml
hierarchy:
  part: Preliminary Title  # ❌ No DB column for "part"
  sections: Articles 7-11  # ❌ No DB column for "sections"
```

**Mismatch**: YAML uses flexible text hierarchy (`part`, `sections`) but schema expects structured numeric fields (`book_number`, `section_number`).

---

## 4. Loader & Validator Implementation

### 4.1 `manual_chunk_loader.py`

**ManualChunk Dataclass**:
```python
@dataclass
class ManualChunk:
    chunk_id: str
    title: str
    content: str
    article_number: str
    semantic_type: Optional[str] = None
    hierarchy: Optional[Dict[str, str]] = None  # ⚠️ Stores as dict, not structured
    keywords: Optional[List[str]] = None
    has_table: bool = False
    has_formula: bool = False
    has_list: bool = False
    
    # Metadata from metadata.json
    source: Optional[str] = None
    reference: Optional[str] = None  # ❌ NOT in schema!
    doc_type: Optional[str] = None
    url: Optional[str] = None
```

**Issues**:
1. ✅ Loads all YAML fields correctly
2. ❌ `chunk_id` is loaded but **never stored** in database
3. ❌ `reference` from metadata.json is loaded but **no DB column**
4. ❌ `semantic_type` loaded but only stored in JSONB metadata
5. ⚠️ `hierarchy` is a flexible dict - no validation against schema structure

### 4.2 `validate_chunks.py`

**Validation Rules**:
```python
required_fields = ['chunk_id', 'title', 'article_number']
recommended_fields = ['keywords', 'semantic_type']
```

**Issues**:
1. ✅ Validates YAML structure
2. ❌ Does NOT validate against database schema
3. ❌ Does NOT warn about fields that will be lost (chunk_id, semantic_type)
4. ❌ Does NOT validate hierarchy structure matches schema expectations

---

## 5. Ingestion Pipeline Analysis

### 5.1 `sync_to_vectorstore.py` - Manual Chunk Ingestion

**Code Analysis** (lines 400-500):
```python
# Convert ManualChunk to metadata
chunk_metadata = {
    "source": manual_chunk.source or source_name,
    "source_id": str(source_id),
    "doc_type": manual_chunk.doc_type or "statute",
    "url": manual_chunk.url or "",
    "short_name": reference,
    "title": manual_chunk.title,
    "article_number": manual_chunk.article_number,
    "has_table": manual_chunk.has_table,
    "has_formula": manual_chunk.has_formula,
    "has_list": manual_chunk.has_list,
    "semantic_type": manual_chunk.semantic_type,  # ⚠️ In metadata, not column
    "hierarchy": manual_chunk.hierarchy or {},  # ⚠️ Stored as JSONB, not extracted
    "keywords": manual_chunk.keywords or [],
    "summary": None  # Will be filled by summarizer
}
```

**Critical Findings**:
1. ❌ **`chunk_id` is NEVER included** in metadata - completely lost
2. ❌ **`hierarchy` stored as JSONB** - NOT extracted to `book`, `title_name`, `chapter` columns
3. ❌ **`semantic_type` stored in JSONB** - no dedicated column (though schema doesn't have one)
4. ⚠️ **No extraction of numeric hierarchy** (book_number, title_number, etc.) from text

### 5.2 `supabase_store.py` - Upsert Mapping

**Code Analysis** (lines 150-190):
```python
record = {
    "id": doc_uuid,
    "full_text": doc.content,
    "embedding": doc.embedding,  # ⚠️ CRITICAL: What is this embedding of?
    "metadata": json.dumps(metadata),
    
    # Extract fields from metadata
    "article_number": metadata.get("article_number", doc.id),
    "article_title": metadata.get("title", ""),
    "summary": metadata.get("summary"),  # ✅ From ChunkSummarizer
    "keywords": metadata.get("keywords", []),
    "book": metadata.get("hierarchy", {}).get("book"),  # ⚠️ Extracts "book" key
    "title_name": metadata.get("hierarchy", {}).get("title"),  # ⚠️ Extracts "title" key
    "chapter": metadata.get("hierarchy", {}).get("chapter"),  # ⚠️ Extracts "chapter" key
    "has_table": metadata.get("has_table", False),
    "has_formula": metadata.get("has_formula", False),
    "has_list": metadata.get("has_list", False),
    "source_id": metadata.get("source_id")
}
```

**Critical Issues**:

1. **Embedding Source**: 
   - Code: `embedding: doc.embedding` 
   - ❌ **UNCLEAR**: Is this embedding of `full_text` or `summary`?
   - ADR-002 requirement: Should be embedding of **summary**

2. **Hierarchy Extraction**:
   - Tries to extract `hierarchy.book`, `hierarchy.title`, `hierarchy.chapter`
   - ❌ **MISMATCH**: 
     - PD-442 YAML uses: `hierarchy.part`, `hierarchy.sections`
     - PD-851 YAML uses: `hierarchy.part`, `hierarchy.sections`
     - Code expects: `hierarchy.book`, `hierarchy.title`, `hierarchy.chapter`
   - **Result**: `book`, `title_name`, `chapter` columns will be **NULL** for all PD-442 and PD-851 chunks!

3. **Missing Fields**:
   - ❌ No extraction of `section_number` (column doesn't exist anyway)
   - ❌ No extraction of `reference` for fast law lookup
   - ❌ No storage of `chunk_id` anywhere

---

## 6. labor_law_chunks Table - When to Use?

### Schema Definition
```sql
CREATE TABLE labor_law_chunks (
    id UUID PRIMARY KEY,
    section_id UUID REFERENCES labor_law_sections(id),
    chunk_index INT NOT NULL,
    chunk_text TEXT NOT NULL,
    summary TEXT,
    keywords TEXT[],
    embedding vector(1536),
    created_at TIMESTAMPTZ
);
```

### ADR-002 Specification
> "Chunk only when article is very long (>1000 words)"

### Use Case (from ADR-002)
```
labor_law_sections:
  - Article 87: "Normal hours of work..." (150 words) → stored as-is
  - Article 123: "Very long article..." (1,500 words) → split into chunks

labor_law_chunks:
  - section_id: Article 123 UUID
    chunk_index: 1
    chunk_text: "First 500 words..."
  - section_id: Article 123 UUID  
    chunk_index: 2
    chunk_text: "Next 500 words..."
```

### Current Implementation Status

**From PD-442 Analysis**:
- Total words: 41,163
- Articles: ~300
- Average: ~137 words/article
- **Articles >1000 words**: Estimated 5-10 only

**Conclusion**: 
- ✅ `labor_law_chunks` is for **sub-chunking individual long articles**
- ✅ NOT for grouping multiple articles
- ⚠️ **Current ingestion pipeline does NOT implement this logic**
  - All chunks go to `labor_law_sections` regardless of size
  - No automatic splitting of >1000 word articles

---

## 7. Critical Misalignments Summary

### 7.1 Schema vs. ADR-002 Architecture

| Issue | ADR-002 Spec | Actual Schema | Impact |
|-------|--------------|---------------|--------|
| Hierarchy types | `book_number INT` | `book VARCHAR(100)` | ❌ Can't sort by book number |
| Title field | `title_number INT` | `title_name VARCHAR(200)` | ❌ Wrong name, can't query by title number |
| Section number | `section_number INT` | ❌ Missing | ❌ Can't identify section position |
| Law reference | `source_reference TEXT` | ❌ Missing | ❌ Can't do fast "PD 851" lookup |
| Embedding source | Summary embedding | ⚠️ Unknown | ⚠️ May not match ADR-002 optimization |
| HNSW index | Required for Strategy 2 | ⚠️ External file | ⚠️ May not be deployed |

### 7.2 YAML Frontmatter vs. Schema

| YAML Field | Schema Column | Status |
|------------|---------------|--------|
| `chunk_id` | ❌ None | ❌ **LOST** - never stored |
| `semantic_type` | ❌ None | ⚠️ Only in JSONB metadata |
| `hierarchy.part` | ❌ None | ❌ **LOST** |
| `hierarchy.sections` | ❌ None | ❌ **LOST** |
| `hierarchy.book` | `book` | ⚠️ Works IF "book" key used (not "part") |
| `hierarchy.title` | `title_name` | ⚠️ Works IF "title" key used |
| `hierarchy.chapter` | `chapter` | ⚠️ Works IF "chapter" key used |

**Current Mismatch**: 
- All PD-442 and PD-851 chunks use `hierarchy.part` and `hierarchy.sections`
- Ingestion code looks for `hierarchy.book`, `hierarchy.title`, `hierarchy.chapter`
- **Result**: Hierarchical columns are **NULL** in database!

### 7.3 metadata.json vs. Database

| metadata.json Field | DB Storage | Status |
|---------------------|------------|--------|
| `source` | `labor_law_sources.title` | ✅ Via source_manager |
| `reference` | ❌ **MISSING COLUMN** | ❌ Critical for Strategy 3 |
| `short_name` | ❌ **MISSING** | ❌ Lost |
| `doc_type` | `labor_law_sources.source_type` | ✅ Via source_manager |
| `url` | `labor_law_sources.official_url` | ✅ Via source_manager |
| `year` | ❌ **MISSING** | ❌ Lost (could be in metadata JSONB) |
| `total_chunks` | ❌ **MISSING** | ❌ Never stored |
| `chunking_strategy` | ❌ **MISSING** | ❌ Never stored |

### 7.4 Embedding Strategy - CRITICAL VIOLATION CONFIRMED ⚠️

**ADR-002 Specification**: 
> "Vector embedding (of summary, not full text)"
> "Summary Embeddings: Semantic search on LLM-generated summaries (better semantic representation than raw legal text)"

**Actual Implementation** (`sync_to_vectorstore.py` line 498):
```python
texts_for_embedding.append(manual_chunk.content)  # ❌ WRONG!
```

**CONFIRMED ISSUE**: 
- ❌ Embeddings are created from **full_text** (`manual_chunk.content`)
- ❌ NOT from summary as ADR-002 specifies
- ❌ This violates the core optimization strategy for semantic search

**Impact**:
1. **Semantic search quality degraded**: Legal text is verbose and technical, summaries are more semantically meaningful
2. **Vector search performance**: Embedding longer text increases dimensionality noise
3. **Strategy 2 not optimized**: ADR-002's 1.8-2.0s target likely won't be met

**Correct Implementation Should Be**:
```python
# Generate summaries first
summaries = await self.summarizer.summarize_batch([chunk.content for chunk in chunks])

# THEN embed the summaries (not full text)
texts_for_embedding = [summary.summary for summary in summaries]
batch_response = await self.embeddings.embed_batch(texts=texts_for_embedding)
```

**Action Required**: Modify ingestion pipeline to embed summaries, not full text.

---

## 8. Recommendations

### 8.1 IMMEDIATE FIXES (Before PD-442 Chunking)

#### Fix 1: Standardize YAML Hierarchy Keys

**Problem**: Current YAML uses `part`/`sections`, code expects `book`/`title`/`chapter`

**Solution**: Update ALL chunk YAML files to use:
```yaml
hierarchy:
  book: "Book One"  # Not "part"
  title: "Pre-Employment"  # New field
  chapter: "Chapter I"  # If applicable
```

**Action**: Update chunks/README.md with correct hierarchy specification.

#### Fix 2: Add Missing Schema Columns

**SQL Migration**:
```sql
-- Add reference column to labor_law_sources for fast lookup
ALTER TABLE labor_law_sources ADD COLUMN IF NOT EXISTS reference VARCHAR(50);
CREATE INDEX IF NOT EXISTS idx_sources_reference ON labor_law_sources(reference);

-- Add year to labor_law_sources
ALTER TABLE labor_law_sources ADD COLUMN IF NOT EXISTS year INT;

-- Add semantic_type to labor_law_sections
ALTER TABLE labor_law_sections ADD COLUMN IF NOT EXISTS semantic_type VARCHAR(50);

-- Add section_number for complete hierarchy
ALTER TABLE labor_law_sections ADD COLUMN IF NOT EXISTS section_number INT;
```

#### Fix 3: Verify Embedding Source

**Investigation Task**: Check `sync_to_vectorstore.py` embedding generation:
- Is it embedding `summary` or `full_text`?
- Update to ensure ADR-002 compliance (summary embeddings)

#### Fix 4: Deploy HNSW Index

**Check**: Does `infra/supabase/create_hnsw_indexes.sql` exist?
**If not**: Create it and deploy HNSW index for Strategy 2 optimization.

### 8.2 MEDIUM PRIORITY (Phase 1.1)

#### Update Hierarchy to Numeric Types

**Rationale**: ADR-002 specifies INT types for proper sorting and querying

**Migration**:
```sql
-- Add new numeric columns
ALTER TABLE labor_law_sections ADD COLUMN book_number INT;
ALTER TABLE labor_law_sections ADD COLUMN title_number INT;
ALTER TABLE labor_law_sections ADD COLUMN chapter_number INT;

-- Migrate data (if possible)
-- UPDATE labor_law_sections 
-- SET book_number = CAST(regexp_replace(book, '[^0-9]', '', 'g') AS INT)
-- WHERE book ~ '^Book [0-9]+';

-- Create indexes
CREATE INDEX idx_sections_book_number ON labor_law_sections(book_number);
CREATE INDEX idx_sections_title_number ON labor_law_sections(title_number);
```

#### Implement Auto-Chunking for Long Articles

**Logic**: If article >1000 words, split into `labor_law_chunks`
**Code Location**: `sync_to_vectorstore.py` ingestion logic

### 8.3 DOCUMENTATION UPDATES

1. **chunks/README.md**:
   - ✅ Clarify hierarchy keys: `book`, `title`, `chapter` (not `part`, `sections`)
   - ✅ Add `semantic_type` to recommended fields
   - ✅ Specify metadata.json should match schema fields

2. **metadata.json specification**:
   - Add fields that will be stored in `labor_law_sources`
   - Remove fields that are never used (total_chunks, chunking_strategy)
   - Document which fields are for tracking vs. database storage

3. **ADR-002 Update**:
   - Document actual schema vs. ideal schema
   - Note current limitations
   - Add migration plan for full compliance

---

## 9. Action Plan for PD-442 Chunking

### Before Starting Manual Chunking:

1. ✅ **Update chunks/README.md** with correct hierarchy specification
2. ✅ **Create template YAML** with correct keys:
   ```yaml
   hierarchy:
     book: "Book One"
     title: "Pre-Employment"  
     chapter: ""  # Optional
   ```
3. ✅ **Update PD-No-851 chunks** to use correct hierarchy keys
4. ❌ **FIX CRITICAL: Change embedding source** from `full_text` to `summary` (line 498 in sync_to_vectorstore.py)
5. ✅ **HNSW index script exists** (`infra/supabase/create_hnsw_indexes.sql`) - need to verify if deployed

### During PD-442 Chunking:

1. Use corrected YAML hierarchy keys
2. Ensure all required fields are present
3. Validate with `validate_chunks.py` before ingestion

### After Chunking:

1. Run schema migration for missing columns
2. Re-ingest PD-No-851 with corrected hierarchy
3. Test multi-strategy retrieval with corrected data

---

## 10. Conclusion

**Critical Findings**:

1. ❌ **Database schema does NOT fully implement ADR-002** architecture
   - Missing `source_reference` for Strategy 3 (fast law lookup)
   - Wrong data types for hierarchical fields (VARCHAR instead of INT)
   - Missing HNSW index deployment status unclear

2. ❌ **YAML frontmatter uses wrong hierarchy keys**
   - Current: `part`, `sections`
   - Expected: `book`, `title`, `chapter`
   - **Impact**: All hierarchical columns are NULL in database!

3. ❌ **metadata.json fields not aligned with database**
   - `reference` field critical but no schema column
   - Many fields lost during ingestion

4. ❌ **Embedding source WRONG - critical violation**
   - ADR-002 requires summary embeddings for better semantic search
   - Current implementation embeds full_text (line 498: `manual_chunk.content`)
   - **Impact**: Strategy 2 optimization will not work as designed

5. ✅ **labor_law_chunks usage now clear**
   - For sub-chunking articles >1000 words
   - NOT currently implemented in ingestion pipeline

**Recommendation**: 
🛑 **PAUSE PD-442 chunking** until:
1. Hierarchy keys standardized in README and templates
2. Embedding source verified
3. Schema gaps documented with migration plan

This investigation is **critical** for ensuring the multi-strategy retrieval architecture will actually work as designed.

---

**Next Steps**:
1. Review this investigation with team
2. Decide on immediate fixes vs. deferred improvements
3. Update documentation and templates
4. Create schema migration script
5. Resume PD-442 chunking with corrected approach
