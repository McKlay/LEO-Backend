# Task 7 — Validation & Testing Guide

**Phase 2: Hybrid Retrieval (Stage 2)**
**Test file:** `tests/unit/test_phase2_hybrid_retrieval.py`

---

## 1. Run the Unit Tests

All unit tests are offline (no live DB or API keys required).

```bash
# Activate venv first if not already active
.venv\Scripts\Activate.ps1

# Run only the Phase 2 hybrid retrieval tests
pytest tests/unit/test_phase2_hybrid_retrieval.py -v

# Run with full log output (shows what INFO logs fire during tests)
pytest tests/unit/test_phase2_hybrid_retrieval.py -v -s
```

### Expected output (all passing)

```
tests/unit/test_phase2_hybrid_retrieval.py::TestRRF::test_single_strategy_preserves_order PASSED
tests/unit/test_phase2_hybrid_retrieval.py::TestRRF::test_same_doc_two_strategies_accumulates_score PASSED
tests/unit/test_phase2_hybrid_retrieval.py::TestRRF::test_three_way_agreement_ranks_first PASSED
tests/unit/test_phase2_hybrid_retrieval.py::TestRRF::test_absent_strategy_no_penalty PASSED
tests/unit/test_phase2_hybrid_retrieval.py::TestRRF::test_empty_strategy_list_skipped PASSED
tests/unit/test_phase2_hybrid_retrieval.py::TestRRF::test_all_empty_returns_empty PASSED
tests/unit/test_phase2_hybrid_retrieval.py::TestRRF::test_rrf_metadata_attached PASSED
tests/unit/test_phase2_hybrid_retrieval.py::TestDirectArticleLookupGIN::test_article_297_returns_primary_section_only PASSED
tests/unit/test_phase2_hybrid_retrieval.py::TestDirectArticleLookupGIN::test_ra_10361_normalization PASSED
tests/unit/test_phase2_hybrid_retrieval.py::TestDirectArticleLookupGIN::test_source_hint_narrows_to_correct_statute PASSED
tests/unit/test_phase2_hybrid_retrieval.py::TestDirectArticleLookupGIN::test_score_not_fixed_at_1 PASSED
tests/unit/test_phase2_hybrid_retrieval.py::TestSmartRetrieveStrategyGating::test_dense_only_ignores_articles_and_keywords PASSED
tests/unit/test_phase2_hybrid_retrieval.py::TestSmartRetrieveStrategyGating::test_empty_set_returns_immediately PASSED
tests/unit/test_phase2_hybrid_retrieval.py::TestSmartRetrieveStrategyGating::test_none_runs_all_applicable_strategies PASSED
tests/unit/test_phase2_hybrid_retrieval.py::TestSmartRetrieveStrategyGating::test_strategy_metadata_tagged_on_results PASSED

15 passed in X.XXs
```

Share the terminal output here if any test fails.

---

## 2. Integration Tests — Pipeline Variant Isolation

These require the backend server running locally with a real `.env`.

### 2.1 Start the server

```bash
uvicorn app.main:app --reload --port 8000
```

### 2.2 Smoke each `retrieval_mode` variant

Override the mode per request by temporarily editing `.env` and restarting, **or** override at runtime if you add a test-only env-override hook. For a quick check, set `RETRIEVAL_MODE` in the shell:

```powershell
# hybrid — all 3 strategies must fire
$env:RETRIEVAL_MODE = "hybrid"
uvicorn app.main:app --port 8000
```

Then send a citation query (symbolic should trigger):

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/v1/chat" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"message": "What does Article 297 say about termination?", "conversation_id": null, "language": "en"}'
```

**What to look for in the uvicorn log:**

| Log line | Confirms |
|---|---|
| `smart_retrieve: active=['dense', 'lexical', 'symbolic']` | All 3 strategies launched |
| `symbolic=N, lexical=N, dense=N -> rrf_merged=M` | RRF ran across 3 lists |
| `strategy_breakdown={'symbolic': X, 'lexical': Y, 'dense': Z}` | Breakdown in `retrieve()` |
| `[1] id=... strategies=['symbolic', ...]` | Per-result attribution log |

---

### 2.3 Variant test matrix

Run the same citation query for each mode and paste the log lines:

```powershell
# dense-only
$env:RETRIEVAL_MODE = "dense"

# lexical-only  
$env:RETRIEVAL_MODE = "lexical"

# symbolic-only
$env:RETRIEVAL_MODE = "symbolic"

# LLM-only (no RAG)
$env:RETRIEVAL_MODE = "none"
```

| `retrieval_mode` | Expected log | Expected response |
|---|---|---|
| `hybrid` | `active=['dense', 'lexical', 'symbolic']` | Citation-grounded answer |
| `dense` | `active=['dense']` | Semantic-only answer |
| `lexical` | `active=['lexical']` | FTS-only answer |
| `symbolic` | `active=['symbolic']` | GIN keyword-only answer |
| `none` | `retrieval_mode=none — skipping retrieval` | Answer with no citations (LLM-only) |

---

## 3. Symbolic Lookup Verification

Verify the GIN fix eliminates cross-reference false positives.

Send an Article 297 query with `retrieval_mode=symbolic`:

```powershell
$env:RETRIEVAL_MODE = "symbolic"
# restart server, then:
Invoke-RestMethod -Uri "http://localhost:8000/v1/chat" `
  -Method POST -ContentType "application/json" `
  -Body '{"message": "Article 297 termination", "conversation_id": null, "language": "en"}'
```

**Pass criteria:**
- All returned citations must be from sections where `Article 297` is a **primary** article ref in `keywords[]` (not a cross-reference mention in `full_text`)
- No result should be a section that only tangentially mentions Article 297

---

## 4. Checklist After Testing

Copy terminal output here or share it so results can be verified.

- [ ] All 15 unit tests pass
- [ ] `hybrid` mode: 3 strategies visible in log
- [ ] `dense` mode: only dense results, no symbolic/lexical log lines
- [ ] `lexical` mode: only lexical results
- [ ] `symbolic` mode: only GIN results, no ILIKE fallback
- [ ] `none` mode: `retrieve()` returns `[]`, no "Searching labor laws..." SSE event
- [ ] Per-result attribution log lines appear for every retrieve call
