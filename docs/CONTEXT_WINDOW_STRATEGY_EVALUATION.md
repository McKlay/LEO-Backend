# Context Window Strategy Evaluation

**Date:** March 26, 2026  
**Status:** Implemented (March 27, 2026)  
**Component:** `services/pipeline/grounding.py` — `build_grounded_prompt()`

---

## 1. Problem Statement

The current `max_context_length` is **8,000 characters (~2,000 tokens)**, while GPT-4.1 supports a **1,048,576-token context window** with 32,768-token output. This aggressively low limit causes **smart truncation to regularly drop retrieved documents down to 1 out of 2–5**, as seen in production logs:

```
Context exceeds 8000 chars (13560 chars), truncating intelligently
Smart truncation: kept 1/2 documents (7967/8000 chars)
```

The system retrieves relevant legal sources but then **discards most of them before the LLM ever sees them**, degrading answer quality, citation coverage, and multi-article reasoning.

---

## 2. Current State Analysis

### 2.1 KB Chunk Size Distribution (166 chunks, excluding metadata)

| Metric | Characters | Est. Tokens |
|--------|-----------|-------------|
| **Average** | 5,302 | ~1,325 |
| **Median** | 4,411 | ~1,103 |
| **P75** | 7,280 | ~1,820 |
| **P90** | 9,652 | ~2,413 |
| **Max** | 26,059 | ~6,515 |
| **Min** | 696 | ~174 |

**Distribution:**
- 0–4,000 chars: 75 chunks (45%) — fit easily
- 4,000–8,000 chars: 64 chunks (39%) — one fills the current budget
- 8,000+ chars: 27 chunks (16%) — **exceed the entire current limit alone**

### 2.2 Current Prompt Token Budget

| Component | Characters | Est. Tokens |
|-----------|-----------|-------------|
| System prompt template (without context) | ~1,000 | ~250 |
| Context (max_context_length) | 8,000 | ~2,000 |
| Conversation history (3 exchanges) | ~2,400 | ~600 |
| User query | ~200 | ~50 |
| **Total input** | **~11,600** | **~2,900** |
| Output (llm_max_tokens) | — | 2,000 |
| **Grand total** | — | **~4,900** |

GPT-4.1 capacity used: **< 0.5%** of the 1M-token window.

### 2.3 Database Schema — Summary Column

Both `labor_law_sections` and `labor_law_chunks` tables have a `summary TEXT` column:
- **Sections:** `summary TEXT` — LLM-generated summary for better semantic search
- **Chunks:** `summary TEXT` — GPT-4o-mini generated summary

These summaries are already retrieved by all strategies (dense, lexical, symbolic) and stored in `QueryResult.metadata["summary"]` but **never used in the grounding prompt**.

---

## 3. Strategy Evaluation

### Option A: Increase to 2–3 Full-Text Documents
**`max_context_length` → 24,000 chars (~6,000 tokens)**

| Criteria | Assessment |
|----------|------------|
| Answer quality | Good — top 2–3 most relevant docs in full |
| Citation coverage | Moderate — still drops docs 4–5 |
| Token cost | Minimal increase (~$0.001/query at GPT-4.1 pricing) |
| Latency | Negligible — GPT-4.1 handles 6K tokens easily |
| Implementation effort | Trivial — change one constant |
| Risk | Low |

**Verdict:** Improvement, but still artificially constraining. Doesn't solve multi-article queries (e.g., "compare retirement benefits across RA 10361 and PD 442").

### Option B: Keep All Documents Full-Text (No Truncation)
**`max_context_length` → 50,000 chars (~12,500 tokens)**

| Criteria | Assessment |
|----------|------------|
| Answer quality | Excellent — LLM sees all retrieved context |
| Citation coverage | Full — all retrieved docs available for citation |
| Token cost | ~$0.003/query (still negligible for GPT-4.1) |
| Latency | Minimal — GPT-4.1 is optimized for long context |
| Implementation effort | Change one constant + increase `llm_max_tokens` |
| Risk | Low — worst case (5 × P90 chunks) ≈ 12,000 tokens, well within budget |

**Verdict:** Simple and effective for a 5-doc retrieval pipeline. However, if `retrieval_top_k` increases later, costs scale linearly with no compression.

### Option C: Top 2–3 Full-Text + Summaries for Remaining *(Recommended)*
**`max_context_length` → 30,000 chars (~7,500 tokens)**

| Criteria | Assessment |
|----------|------------|
| Answer quality | Excellent — primary docs in full, secondary docs summarized |
| Citation coverage | Full — all docs contribute, primary docs anchor citations |
| Token cost | ~$0.002/query — compressed tail keeps costs stable |
| Latency | Negligible |
| Implementation effort | Moderate — change formatting logic + truncation strategy |
| Risk | Low — graceful degradation; summaries already exist in DB |
| Scalability | Good — can increase `top_k` to 8–10 without proportional cost growth |

**How it works:**
1. Documents sorted by relevance score (existing behavior)
2. Top N docs (configurable, default 3): include **full `content`**
3. Remaining docs: include **`metadata["summary"]`** with full citation headers
4. If no summary exists for a doc, fall back to first 500 chars + `[truncated]`

**Why this is best:**
- GPT-4.1 gets complete legal text for the most relevant articles (precise citations)
- Lower-ranked docs provide topical awareness without token bloat
- Summaries are LLM-generated and already optimized for semantic density
- Future-proof: if `top_k` grows to 10, only top 3 are full-text, rest are summaries

### Option D: Summaries for All Documents
**`max_context_length` → 10,000 chars (~2,500 tokens)**

| Criteria | Assessment |
|----------|------------|
| Answer quality | Degraded — loses specific legal text, clause wording, formulas |
| Citation coverage | Weak — summaries lack precise article text for inline citations |
| Token cost | Lowest |
| Latency | Fastest |
| Implementation effort | Moderate — change formatting to use summary field |
| Risk | **High** — legal chatbot requires exact wording for credibility |

**Verdict:** Rejected. A citation-driven legal chatbot **must** have access to exact legal text for at least the primary sources. Summaries lose the precision that makes LEO trustworthy.

---

## 4. Decision: Option B — All Documents Full-Text

With `retrieval_top_k` fixed at 5, Option C's hybrid approach is unnecessary complexity. At `top_k=5`, the worst case (5 × P90 = 48,260 chars, ~12,065 tokens) is trivially within GPT-4.1's 1M-token window. Option B delivers maximum context quality with minimal code change.

### 4.1 Configuration Changes

| Setting | Old | New | File |
|---------|-----|-----|------|
| `max_context_length` | 8,000 | **50,000** | `core/config.py` (default) |
| `LLM_MAX_TOKENS` | 2,000 | **4,000** | `.env` |

No new settings or logic changes required — the existing `_format_rich_context()` and `_smart_truncate_context()` are sufficient; smart truncation becomes a near-never-triggered safety net rather than a regular code path.

### 4.2 Token Budget After Changes

| Component | Characters | Est. Tokens |
|-----------|-----------|-------------|
| System prompt template | ~1,000 | ~250 |
| Context — 5 docs, average case | ~27,040 | ~6,760 |
| Context — 5 docs, P90 case | ~48,260 | ~12,065 |
| Conversation history (3 exchanges) | ~2,400 | ~600 |
| User query | ~200 | ~50 |
| **Total input (avg)** | **~30,640** | **~7,660** |
| **Total input (P90)** | **~51,860** | **~12,965** |
| Output (`llm_max_tokens`) | — | 4,000 |

GPT-4.1 capacity used: **~1–1.5%**. Cost delta: ~$0.001–0.002/query. No latency concern.

### 4.3 Worst-Case Analysis

| Scenario | Context chars | Context tokens | Fits in 50K limit? |
|----------|--------------|----------------|---------------------|
| 5 × median chunks (4,411 chars) | 22,585 | ~5,646 | Yes |
| 5 × P90 chunks (9,652 chars) | 48,260 | ~12,065 | Yes |
| 4 × P90 + 1 × max outlier (26,059) | 64,667 | ~16,167 | No → smart truncation fires |
| 5 × max outlier (26,059) | 130,295 | ~32,574 | No → smart truncation fires |

The outlier (26,059-char DOLE Handbook TOC chunk) is the only realistic trigger for smart truncation; it is unlikely to be retrieved alongside 4 other P90-sized docs simultaneously.

---

## 5. Files Modified

| File | Change |
|------|--------|
| [core/config.py](core/config.py) | `max_context_length` default: `8000` → `50000` |
| `.env` | `LLM_MAX_TOKENS`: `2000` → `4000` |

---

## 6. Verification

After the fix, the truncation warning should no longer appear for typical queries:

```
# Before:
Context exceeds 8000 chars (13560 chars), truncating intelligently
Smart truncation: kept 1/2 documents (7967/8000 chars)

# After (expected for the same query):
Formatted 2 documents into rich context (13560 chars)
Built grounded prompt: 2 documents, 2 total messages, system_prompt=14700 chars
```

Test query from logs:
> "What does Article 87 of the Labor Code provide regarding overtime work?"

Expected: Both retrieved documents appear in full, no truncation warning.
