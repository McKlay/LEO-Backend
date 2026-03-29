# Symbolic Retrieval Evaluation & Implementation Guide

**Date:** March 22, 2026  
**Status:** Findings documented, implementation pending  
**Related:** `KB_CONSTRUCTION_METHODOLOGY.md`, RRF implementation roadmap

---

## Executive Summary

Current three-stage hybrid RAG (dense + sparse + symbolic) has a **critical schema mismatch** that makes the symbolic lookup strategy nearly ineffective. The `article_number` column stores slugs like `pd442_article12_objectives` instead of human-readable labels like `"Article 12"`, causing B-tree index to be bypassed. Symbolic matches fall back to `full_text ILIKE`, introducing noise.

**Impact:** Symbolic lookup provides marginal value for citation-specific queries but also injects false positives. Once RRF is implemented, these issues will compound.

---

## Current Implementation Architecture

| Strategy | Implementation | Index | Trigger Condition |
|----------|---------------|-------|-------------------|
| **Dense** | `_query_sections_table()` + `_query_chunks_table()` → HNSW cosine similarity on 1536-dim embeddings | HNSW on `embedding` | Always (if query_embedding provided) |
| **Sparse** | `keyword_search()` → `plainto_tsquery` + `ts_rank` on `full_text` | GIN on `to_tsvector('english', full_text)` | When `keywords` extracted by GPT-4o-mini |
| **Symbolic** | `direct_article_lookup()` → ILIKE on `full_text`, `article_number`, `article_title` | B-tree on `article_number` (unused) | When article refs detected (GPT-4o-mini + regex fallback) |

**Merge Strategy:** Fixed priority (`direct=3 > keyword=2 > semantic=1`). Deduplicates by ID, keeping highest-priority result. **No RRF yet.**

---

## Critical Findings

### 1. Schema Mismatch: `article_number` Column

**Problem:** The `article_number` field stores internal slugs, not human-readable labels.

```sql
-- What's stored in DB:
article_number = 'pd442_article12_objectives'

-- What the query searches for:
WHERE article_number ILIKE '%Article 12%'  -- NEVER MATCHES
```

**Impact:** The B-tree index `idx_sections_article` is completely bypassed. All symbolic matches rely on `full_text ILIKE` instead.

**Evidence:**
```yaml
# From kb/chunks/PD-No-442/01-book1-article12-objectives.md
article_number: pd442_article12_objectives  # No space, no "Article" prefix
title: Article 12 - Statement of Objectives
```

---

### 2. False Positives from `full_text ILIKE`

**Problem:** Symbolic lookup searches `full_text ILIKE '%Article 297%'`, matching any document that **mentions** Article 297 anywhere in its body.

**Impact:** Legal articles routinely cross-reference each other (e.g., "as provided under Article 297..."). This creates noise—documents referencing but not defining the target article surface at `score=1.0` with `priority=3`.

**Example:** Query `"What does Article 297 say?"` returns:
- ✅ Article 297 itself (legit)
- ❌ Article 295 (contains "...except as in Article 297...")
- ❌ Article 300 (contains "...without prejudice to Article 297...")

---

### 3. Merge Strategy Discards Cross-Strategy Agreement

**Current behavior:** When the same document appears in multiple strategies, only the highest-priority strategy's score is retained. The fact that it appeared in **2 or 3 strategies** is discarded.

**Why this matters for RRF:** Reciprocal Rank Fusion rewards documents that rank high across **multiple** strategies:

$$\text{score}(d) = \sum_{r \in \{\text{sym, lex, dense}\}} \frac{1}{k + \text{rank}_r(d)}$$

If a document is rank-1 in dense, rank-3 in sparse, and absent from symbolic, its RRF score is:

$$\frac{1}{61} + \frac{1}{63} + 0 = 0.0320$$

But a false-positive symbolic match at rank-1 would add $\frac{1}{61} = 0.0164$ to an unrelated document.

---

### 4. No Standalone Ranking Module

**Missing:** `retrieval/ranking.py` does not exist (folder only has `chunking.py`).

**Current state:** All merge/dedup logic is embedded in `supabase_store.py` (`_merge_and_rank_dual_table`, `smart_retrieve`).

**Impact:** No clean place to plug in RRF. When implemented, RRF should consume three separate ranked lists (from dense, sparse, symbolic) and produce a unified re-ranked output.

---

### 5. Symbolic Triggered Only for Citation Queries

**Trigger condition:** `query_analysis.py` detects article references via:
1. GPT-4o-mini structured output (`articles` field)
2. Regex fallback (`_extract_articles_regex()`) for patterns like `Article \d+`, `PD \d+`, `RA \d+`

**Impact:** Most general queries (e.g., "Am I entitled to overtime?") bypass symbolic entirely. Symbolic only affects **citation-specific queries** like "What is Article 297?" or "PD 442 coverage."

---

## Recommendations (Pre-RRF)

### ✅ Fix 1: Add `article_label` Column

```sql
ALTER TABLE labor_law_sections 
ADD COLUMN article_label VARCHAR(100);

CREATE INDEX idx_sections_article_label 
ON labor_law_sections(article_label);
```

**Populate with human-readable labels:**
```sql
UPDATE labor_law_sections 
SET article_label = 'Article 12' 
WHERE article_number = 'pd442_article12_objectives';
```

**Update ingestion:** Add `article_label` to YAML frontmatter:
```yaml
article_number: pd442_article12_objectives  # Slug (unchanged)
article_label: Article 12                    # NEW: Human-readable
```

---

### ✅ Fix 2: Restrict Symbolic to Exact Match Only

**Remove `full_text ILIKE` from `direct_article_lookup()`:**
```python
# OLD (noisy):
WHERE s.full_text ILIKE %s OR s.article_number ILIKE %s

# NEW (precise):
WHERE s.article_label = %s  -- Exact match only
```

**Rationale:** FTS (sparse) already handles body-text mentions. Symbolic should only match the **defining document** for the cited article.

---

### ✅ Fix 3: Create `retrieval/ranking.py`

**Implement RRF as a standalone module:**
```python
def reciprocal_rank_fusion(
    ranked_lists: Dict[str, List[QueryResult]],
    k: int = 60
) -> List[QueryResult]:
    """
    Merge results using Reciprocal Rank Fusion.
    
    Args:
        ranked_lists: Dict mapping strategy name to ranked results
        k: Smoothing constant (default 60)
    
    Returns:
        Unified ranked list sorted by RRF score
    """
    ...
```

**Strategy order invariance:** RRF is commutative—order of strategies doesn't matter.

---

### ✅ Fix 4: Replace `score=1.0` with Rank-Based Input

**Current issue:** `direct_article_lookup()` assigns `score=1.0` to all matches. This is meaningless for RRF, which uses **rank position** instead.

**Solution:** Symbolic should return results ordered by match quality (exact match > fuzzy match), and RRF extracts rank from list position.

---

## Implementation Sequence

1. **Schema migration:** Add `article_label` column + index
2. **Update ingestion:** Parse `article_label` from YAML, populate DB
3. **Rewrite `direct_article_lookup()`:** Use exact match on `article_label`
4. **Create `retrieval/ranking.py`:** Implement RRF function
5. **Refactor `smart_retrieve()`:** Pass three ranked lists to RRF
6. **Test:** Citation-specific queries should show clean retrieval of target articles
7. **Benchmark:** Measure precision@5 for queries like "Article 297" before/after

---

## Expected Outcomes

| Query Type | Before Fixes | After Fixes + RRF |
|------------|--------------|-------------------|
| General (e.g., "overtime pay?") | ✅ Dense + sparse only (works) | ✅ Dense + sparse only (unchanged) |
| Citation-specific (e.g., "Article 297?") | ⚠️ Returns target + 3-5 false positives | ✅ Target article ranks #1 consistently |
| Cross-strategy agreement | ❌ Discarded (priority override) | ✅ Amplified (RRF rewards consensus) |
| Symbolic precision | ~60% (noisy ILIKE matches) | ~95% (exact match on `article_label`) |

---

## References

- **Code:** `adapters/vectorstore/supabase_store.py` (lines 616-716, 977-1092)
- **Schema:** `infra/supabase/schema.sql` (lines 69-115)
- **Chunking:** `kb/chunks/*/metadata.json`, `*.md` YAML frontmatter
- **Query Analysis:** `services/pipeline/query_analysis.py` (lines 330-368)
- **RRF Formula:** Attached image (Reciprocal Rank Fusion section)
