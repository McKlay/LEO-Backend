# PD-No-442 Chunking Analysis Report

**Date**: November 16, 2025  
**Analyzed By**: GitHub Copilot  
**Purpose**: Evaluate chunking strategy for PD-No-442 (Labor Code)

---

## Executive Summary

After analyzing the 63 manually chunked files for PD-No-442, I identified two key issues:

1. **Article Overlap (59 & 60)**: Articles 267-271 appear in BOTH chunks — this is **NOT intended** and creates duplication
2. **Oversized Chunks**: 23 chunks exceed 800 words (guideline: 200-800), with the largest at **2,571 words**

### Recommendations

- **Fix article overlap** by reorganizing chunks 59-60
- **Re-evaluate oversized chunks** based on `labor_law_chunks` table purpose
- **Implement auto-chunking** for articles >1000 words into `labor_law_chunks` table

---

## Issue 1: Article Overlap Analysis

### The Problem

**Chunk 59** (`59-book5-title8-chapter1-4-articles264-272-prohibited-acts-penalties.md`):
- **Declared scope**: Articles 264-272
- **Actual content**: Articles 264, 265, 266, **267-271 are MISSING**, 272
- **Word count**: 895 words

**Chunk 60** (`60-book5-title8-chapter2-3-articles267-271-assistance-foreign-activities.md`):
- **Declared scope**: Articles 267-271
- **Actual content**: Articles 267, 268, 269, 270, 270-A, 271
- **Word count**: 644 words

### Source Document Order

According to `PD-No-442.txt`, the articles appear in this sequence:

```
Article 264 - Prohibited activities (Chapter 1)
Article 265 - Improved offer balloting (Chapter 1)
Article 266 - Requirement for arrest and detention (Chapter 1)
---- Chapter 2: Assistance to Labor Organizations ----
Article 267 - Assistance by DOLE
Article 268 - Assistance by Institute for Labor Studies
---- Chapter 3: Foreign Activities ----
Article 269 - Prohibition against aliens
Article 270 - Regulation of foreign assistance
Article 270-A - Definition of "trade union activities"
Article 271 - Applicability to farm tenants
---- Chapter 4: Penalties for Violation ----
Article 272 - Penalties
```

### Root Cause

The chunking attempted to group **topically related** content:
- **Chunk 59**: "Prohibited Activities + Penalties" (Chapters 1 & 4)
- **Chunk 60**: "Assistance + Foreign Activities" (Chapters 2 & 3)

However, this creates **logical inconsistency**:
- Chunk 59's title says "Articles 264-272" but skips 267-271
- Articles 267-271 appear ONLY in Chunk 60 (not duplicated, but misleading title)

### Is This Intended?

**NO** — This is **poor chunking structure**, not intentional semantic overlap.

**Evidence**:
1. Chunk 59's title claims coverage of Articles 264-272, but text only contains 264-266 and 272
2. No actual duplication in content (267-271 appear only in Chunk 60)
3. Violates chunking guideline: "preserve hierarchical structure"

### Recommended Fix

**Option A: Sequential Chunking (Preferred)**

Split into 3 chunks following document order:

```markdown
59-book5-title8-chapter1-articles264-266-prohibited-acts.md
   - Articles 264-266 (Chapter 1: Prohibited Activities)
   - ~600 words

60-book5-title8-chapter2-3-articles267-271-assistance-foreign.md
   - Articles 267-271 (Chapters 2-3: Assistance + Foreign Activities)
   - ~644 words (no change)

61-book5-title8-chapter4-article272-penalties.md
   - Article 272 (Chapter 4: Penalties)
   - ~250 words
```

**Option B: Topical Chunking (If semantic grouping is critical)**

Keep current structure but fix titles:

```markdown
59-book5-title8-chapter1-articles264-266-prohibited-acts.md
   - Articles 264-266 only
   - ~600 words

60-book5-title8-chapter2-3-articles267-271-assistance-foreign.md
   - Articles 267-271 (no change)
   - ~644 words

61-book5-title8-chapter4-article272-penalties.md
   - Article 272 + cross-reference to Article 264
   - ~250 words
```

**Recommendation**: Use **Option A** for consistency with other chunks.

---

## Issue 2: Oversized Chunks Analysis

### Guideline Violation

**Manual Chunking Guideline** (from `kb/chunks/README.md`):
> **Target**: 200-800 words per chunk  
> **Flexible**: Semantic completeness > strict word count  
> **Exception**: Tables, formulas, lists must remain intact

**Result**: 23 of 63 chunks (36.5%) exceed 800 words.

### Chunks Exceeding 800 Words

| File | Word Count | Violation |
|------|-----------|-----------|
| `49-book5-title2-chapter2-3-articles217-225-nlrc-powers.md` | **2,571** | 321% over |
| `63-book6-title2-book7-articles287-302-retirement-penal-provisions.md` | 1,665 | 208% over |
| `61-book5-title9-articles273-277-special-provisions.md` | 1,596 | 200% over |
| `56-book5-title7-articles250-259-collective-bargaining.md` | 1,383 | 173% over |
| `41-book4-title2-ch3-articles176-182-administration-ecc.md` | 1,259 | 157% over |
| `48-book5-title2-chapter1-articles213-216-nlrc-creation.md` | 1,240 | 155% over |
| `44-book4-title2-ch7-ch8-articles194-204-death-benefits.md` | 1,226 | 153% over |
| `58-book5-title8-chapter1-article263-strikes-lockouts-policy.md` | 1,216 | 152% over |
| `39-book4-title2-ch1-articles166-167-policy-definitions.md` | 1,209 | 151% over |
| `55-book5-title6-articles247-249-unfair-labor-practices.md` | 1,187 | 148% over |
| `33-book3-title3-ch1-articles130-138-employment-women.md` | 1,174 | 147% over |
| `62-book6-title1-articles278-286-termination-employment.md` | 1,119 | 140% over |
| `31-book3-title2-articles123-127-wage-standards.md` | 1,073 | 134% over |
| `51-book5-title4-chapter1-articles234-240-union-registration.md` | 1,061 | 133% over |
| `53-book5-title4-chapter2-article241-part2-financial-accountability.md` | 1,055 | 132% over |
| `47-book5-title1-articles211-212-labor-relations-policy.md` | 1,028 | 129% over |
| `43-book4-title2-ch6-articles191-193-disability-benefits.md` | 1,000 | 125% over |
| `50-book5-title3-articles226-233-bureau-labor-relations.md` | 948 | 119% over |
| `57-book5-title7a-articles260-262b-grievance-voluntary-arbitration.md` | 935 | 117% over |
| `32-book3-title2-articles128-129-wage-administration.md` | 918 | 115% over |
| `23-book3-title1-articles82-90-hours-of-work.md` | 908 | 114% over |
| `59-book5-title8-chapter1-4-articles264-272-prohibited-acts-penalties.md` | 895 | 112% over |
| `24-book3-title1-articles91-96-weekly-rest-holidays.md` | 858 | 107% over |

---

## Purpose of `labor_law_chunks` Table

### Schema Definition (from `infra/supabase/schema.sql`)

```sql
-- Labor law chunks (for very long articles that need splitting)
-- Day 4: Enhanced with summary and keywords columns
CREATE TABLE IF NOT EXISTS labor_law_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section_id UUID REFERENCES labor_law_sections(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    chunk_text TEXT NOT NULL,
    summary TEXT,  -- Day 4: GPT-4o-mini generated summary
    keywords TEXT[],  -- Day 4: Extracted legal keywords
    embedding vector(1536),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Design Intent (from ADR-002)

> **Chunk only when article is very long (>1000 words)**

The `labor_law_chunks` table is designed for **automatic sub-chunking** of oversized articles **after** they are stored in `labor_law_sections`.

### Current Architecture

```
Manual Chunking (kb/chunks/)
  ↓
  Ingestion → labor_law_sections (full article text)
  ↓
  [OPTIONAL] Auto-chunking for >1000 word articles
  ↓
  labor_law_chunks (sub-chunks with embeddings)
```

### Key Insights

1. **Two-level hierarchy**:
   - `labor_law_sections`: Store semantically complete articles/sections
   - `labor_law_chunks`: Auto-split oversized articles for better retrieval

2. **Manual chunks go to `labor_law_sections`**, NOT `labor_law_chunks`
   - Each `.md` file = 1 row in `labor_law_sections`
   - If article >1000 words, ingestion pipeline auto-creates `labor_law_chunks`

3. **Threshold**: 1000 words (from ADR-002 comment)
   - Manual chunks at 800 words are **acceptable** (no auto-chunking)
   - Manual chunks at 2000+ words **should trigger auto-chunking**

---

## Recommendations

### 1. Fix Article Overlap (Critical)

**Action**: Reorganize chunks 59-61 to follow sequential article order.

**Before**:
```
59-book5-title8-chapter1-4-articles264-272-prohibited-acts-penalties.md (264-266, 272)
60-book5-title8-chapter2-3-articles267-271-assistance-foreign-activities.md (267-271)
61-book5-title9-articles273-277-special-provisions.md
```

**After**:
```
59-book5-title8-chapter1-articles264-266-prohibited-acts.md (264-266 only)
60-book5-title8-chapter2-3-articles267-271-assistance-foreign.md (267-271, no change)
61-book5-title8-chapter4-article272-penalties.md (272 only)
62-book5-title9-articles273-277-special-provisions.md (renumbered from 61)
```

### 2. Handle Oversized Chunks (Advisory)

**For chunks 800-1000 words**: No action needed
- Within acceptable tolerance
- Semantic completeness justified

**For chunks >1000 words** (17 chunks):

**Option A: Accept as-is** (Recommended)
- These are **semantically complete** legal sections
- Splitting would break context (e.g., NLRC Powers in Article 217-225)
- Let ingestion pipeline auto-chunk into `labor_law_chunks` if needed

**Option B: Manual re-chunking**
- Split large chunks by sub-articles
- Example: Split Articles 217-225 (2,571 words) into:
  - `217-jurisdiction.md` (800 words)
  - `218-220-powers.md` (800 words)
  - `221-225-appeals.md` (900 words)
- **Risk**: May break legal context and cross-references

**Recommendation**: **Option A** — accept large chunks, rely on auto-chunking during ingestion.

### 3. Update Ingestion Pipeline (Enhancement)

**Current behavior**: Ingest entire manual chunk into `labor_law_sections`

**Proposed enhancement**:
```python
def ingest_manual_chunk(chunk_file):
    # 1. Insert into labor_law_sections (full text)
    section_id = insert_section(chunk_data)
    
    # 2. If word_count > 1000, auto-chunk
    if word_count > 1000:
        sub_chunks = auto_chunk_by_paragraphs(chunk_data.full_text)
        for idx, sub_chunk in enumerate(sub_chunks):
            insert_into_labor_law_chunks(
                section_id=section_id,
                chunk_index=idx,
                chunk_text=sub_chunk,
                summary=generate_summary(sub_chunk),
                keywords=extract_keywords(sub_chunk)
            )
```

**Benefits**:
- Preserves semantic completeness in `labor_law_sections`
- Enables fine-grained retrieval via `labor_law_chunks`
- No need to manually re-chunk large articles

---

## Conclusion

### Article Overlap
- **Status**: ❌ **Not intended** — misleading title in chunk 59
- **Action**: Reorganize chunks 59-61 to fix numbering

### Oversized Chunks
- **Status**: ⚠️ **Acceptable with caveats**
- **Rationale**: Semantic completeness > strict word count
- **Action**: Implement auto-chunking in ingestion pipeline for >1000 word articles

### Next Steps
1. Fix chunks 59-61 article overlap
2. Implement auto-chunking logic in `kb.ingest.sync_to_vectorstore`
3. Test ingestion with oversized chunks to verify `labor_law_chunks` population
4. Update README.md with clarified guidance on chunk sizes vs. auto-chunking

---

## Appendix: labor_law_chunks Usage Pattern

### When to Use `labor_law_chunks`

**Scenario 1: User Query Retrieval**
```sql
-- Multi-strategy retrieval
SELECT * FROM labor_law_sections WHERE article_number = 'Article 217';
-- If this returns >1000 word article, also search chunks:
SELECT * FROM labor_law_chunks WHERE section_id = '...';
```

**Scenario 2: Semantic Search**
```sql
-- Search both sections and chunks
SELECT * FROM labor_law_sections WHERE embedding <=> $query_embedding < 0.3
UNION ALL
SELECT * FROM labor_law_chunks WHERE embedding <=> $query_embedding < 0.3;
```

**Scenario 3: Context Window Optimization**
- If section is too large for LLM context, retrieve specific chunks
- Use chunk summaries to rank relevance before sending full text

### Trade-offs

**Pros**:
- Better granularity for long articles
- Faster semantic search (smaller embedding space)
- More precise retrieval for specific sub-topics

**Cons**:
- Increased storage (duplicate content)
- More complex retrieval logic
- Risk of losing context across chunk boundaries

**Recommendation**: Use `labor_law_chunks` sparingly, only for >1000 word articles where splitting improves retrieval quality.
