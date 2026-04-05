# Phase 3 — Benchmark Implementation Checklist

Reference: [`PHASE_3_AUTOMATED_TESTING_SPECIFICATION.md`](PHASE_3_AUTOMATED_TESTING_SPECIFICATION.md)

---

## Milestone 1: Project Scaffolding

- [x] Create directory structure:
  ```
  tests/benchmark/
  ├── __init__.py
  ├── runner.py
  ├── config.py
  ├── collector.py
  ├── scorers/
  │   ├── __init__.py
  │   ├── retrieval.py
  │   ├── answer_quality.py
  │   ├── citation.py
  │   ├── clarification.py
  │   └── rag_triad.py
  ├── exporters/
  │   ├── __init__.py
  │   ├── csv_exporter.py
  │   └── chart_generator.py
  ├── data/
  │   └── benchmark-queries.json
  └── results/            # gitignored
  ```
- [x] Add `results/` to `.gitignore`
- [x] Copy `benchmark-queries.json` into `tests/benchmark/data/`
- [x] Add benchmark dependencies to `requirements.txt`: `rouge-score`, `matplotlib`, `seaborn`, `pandas`

---

## Milestone 2: Variant Configuration (`config.py`)

- [x] Define `VariantConfig` dataclass (§2) with fields: `name`, `retrieval_mode`, `enable_query_analysis`, `enable_translation`, `enable_smart_clarification`, `query_filter`
- [x] Define `VARIANTS` list with all 8 preset configurations
- [x] Implement `apply_variant(variant)` — overrides `settings` attributes in-place
- [x] Implement `reset_singletons()` — clears `lru_cache` on container functions + resets global module-level singletons in `app.containers`
- [x] Implement `get_queries_for_variant(variant, all_queries)` — filters queries by `query_filter` (`all` / `non_english` / `ambiguous`)

---

## Milestone 3: Result Collector (`collector.py`)

- [x] Define `QueryTrace` dataclass (§3.2) capturing Stage 1, 2, 3 outputs + gold standard + flags
- [x] Implement `ResultCollector.process_event(event)` — parses SSE events into `QueryTrace` fields
- [x] Handle event types: `status`, `metadata`, `content_chunk`, `citations`, `complete`
- [x] Implement `finalize_variant(variant_name)` — seals results for a completed variant
- [x] Implement multi-turn conversation history injection (§3.3) — create fresh `conversation_id`, inject prior turns, send final turn
- [x] Persist partial results to disk (JSON) after each query–variant pair for resume support (§7.4)

---

## Milestone 4: Benchmark Runner (`runner.py`)

### 4a: Core Runner

- [x] Implement `BenchmarkRunner` class with async orchestration loop (§3.1)
- [x] Load benchmark queries from JSON
- [x] For each variant: call `apply_variant()` → `reset_singletons()` → loop queries → call `process_message_stream()` → collect events
- [x] Import pipeline components via `app.containers` (in-process, no uvicorn — §3.8)
- [x] Add configurable API delay between calls (`--api-delay-ms`, default 200ms)
- [x] Implement resume logic — skip query–variant pairs found in existing results (`--resume`)

### 4b: Execution Modes (§3.6)

- [x] `analysis_only` — run Stage 1 only, record `QueryAnalysis` output, skip retrieval + generation
- [x] `retrieval_only` — run Stage 1 + Stage 2, record retrieved chunks at max(K), compute metrics at each K from subsets, skip generation
- [x] `full` — run all three stages (default)
- [x] Multi-K support: single retrieval call at `max(top_k)`, slice results for lower K values

### 4c: CLI Interface (§3.5)

- [x] Parse arguments: `--mode`, `--variant`, `--top-k`, `--query-ids`, `--output-dir`, `--resume`
- [x] Parse validation/debug arguments: `--smoke`, `--validate`, `--log-level`, `--log-file`, `--log-per-variant`, `--quiet`, `--api-delay-ms`
- [x] Wire logging via `core.logging` with `query_id`/`variant` context injection (§3.8)
- [x] Entry point: `python -m tests.benchmark.runner`

### 4d: Pre-flight Validation (§3.7)

- [x] `--smoke` — run 5 representative queries (1 EN single-turn clear, 1 FIL, 1 CEB, 1 multi-turn, 1 ambiguous) through full pipeline, print diagnostic summary
- [x] `--validate clarification` — run 30 ambiguous + 20 non-ambiguous queries through `analysis_only`, report precision/recall of clarification detection
- [x] `--validate multiturn` — run 24 multi-turn queries through `analysis_only` with history injection, verify: history injected, consolidated `normalized_query_en`, no re-clarification, no false `is_meta_conversational`
- [x] `--validate all` — run both in sequence

---

## Milestone 5: Automated Scorers (`scorers/`)

### 5a: Retrieval Metrics (`retrieval.py`) — §4.1

- [x] Recall@K: `|gold ∩ retrieved@K| / |gold|`
- [x] Hit Rate@K: `1 if gold ∩ retrieved@K else 0`
- [x] MRR: `1 / rank_of_first_gold_chunk`
- [x] Chunk ID normalization (strip `kb/chunks/` prefix, compare folder + basename)
- [x] Support K = 3, 5, 10

### 5b: Answer Quality (`answer_quality.py`) — §4.2

- [x] Token F1: word-level precision/recall after lowercase + strip punctuation
- [x] ROUGE-L via `rouge-score` library
- [x] Exact Match after whitespace/case normalization

### 5c: Citation Metrics (`citation.py`) — §4.3

- [x] Regex extraction of citations from generated text (`Article 297`, `Art. 99`, `RA 6727`, `PD 442`)
- [x] Citation normalization (`Art. 297` == `Article 297`)
- [x] Citation precision and recall vs `gold_article_refs`

### 5d: Clarification Metrics (`clarification.py`) — §4.4

- [x] Compute TP/FP/FN on 30 ambiguous queries
- [x] Detection precision and recall

### 5e: RAG Triad (`rag_triad.py`) — §4.5

- [x] GPT-4.1 rubric prompt for 3 dimensions: Context Relevance, Groundedness, Answer Relevance
- [x] Score each query–variant pair: send `(query, retrieved_chunks, answer)` to evaluator
- [x] Skip Context Relevance + Groundedness for `llm_only` variant (no retrieval)
- [x] Separate CLI trigger: `--rag-triad --input results/run_XXX/raw`

---

## Milestone 6: Exporters (`exporters/`)

### 6a: CSV Exporter (`csv_exporter.py`) — §5

- [x] Expert evaluation CSV (§5.1): blinded, randomized config labels (X/Y/Z), shuffled rows, columns for expert scoring
- [x] Produce for 3 configs only: LLM-only, Stage 2 Only, Full Pipeline
- [x] Multi-turn conversation history CSV (§5.2): full dialog per query–variant
- [x] Raw results CSV (§5.3): all 680 runs with all metrics + generated/reference answers
- [x] Store blinding mapping file separately
- [x] CLI: `python -m tests.benchmark.exporters.csv_exporter --input ... --output ... --expert-blind`

### 6b: Chart Generator (`chart_generator.py`) — §6

- [x] 6.1 — Retrieval comparison grouped bar (Table 2): Dense/Lexical/Symbolic/Hybrid × Recall@3/5/10, Hit Rate@5, MRR
- [x] 6.2 — Retrieval by target subset heatmap (Table 3): MRR + Recall@5 per `retrieval_target` subset
- [x] 6.3 — Translation impact grouped bar (Table 4): with/without translation × Filipino/Cebuano/English
- [x] 6.4 — Answer quality grouped bar (Table 6): Config A/B/C × Mean Expert Score, Token F1, ROUGE-L
- [x] 6.5 — Hallucination & citation bar (Table 9): hallucination rate, fabricated citation rate, citation P/R
- [x] 6.6 — RAG Triad radar chart (Table 10): Config B vs C on 3 axes
- [x] 6.7 — Ablation heatmap (Table 11): 8 variants × 5 key metrics
- [x] 6.8 — Per-topic horizontal bar (Recall@5 or MRR by 19 topic categories)
- [x] Output PDF + PNG at 300 DPI, consistent academic palette
- [x] CLI: `python -m tests.benchmark.exporters.chart_generator --input ... --output ...`

---

## Milestone 7: Integration & Execution

- [x] Verify `benchmark-queries.json` schema: 100 queries, all required fields (`gold_chunks`, `gold_article_refs`, `reference_answer`, `conversation_history` for multi-turn, `expected_clarification` for ambiguous); all 30 multi-turn queries additionally have Phase 2 fields (`turn5_query`, `turn6_reference_answer`, `gold_chunks_turn6`, `gold_article_refs_turn6`) (Decisions 3 & 6)
- [x] End-to-end dry run: `--smoke` passes on all 5 representative queries
- [ ] Run `--validate all` — clarification pre-flight diagnostic passes; multi-turn validation passes ≥ 30/30 queries
- [ ] Execute Phase 1 retrieval-only runs (Tables 2–4 + ablation retrieval metrics):
  - `full_pipeline dense_only lexical_only symbolic_only` at K = 3, 5, 10 (Tables 2–3)
  - `full_pipeline hybrid_no_translation` at K = 5, non-English scope 65 queries (Table 4)
  - `hybrid_no_clarification` at K = 3, 5, 10, ambiguous scope 30 queries (Table 11 retrieval slice)
- [ ] Review retrieval metrics before proceeding to Phase 2
- [ ] Execute Phase 2 full pipeline runs (Tables 6–11):
  - Expert variants `llm_only stage2_only full_pipeline` — all 100 queries; multi-turn queries automatically trigger Phase 2 (Turns 5–6) for Table 8 (Decision 3)
  - Remaining ablation variants `dense_only lexical_only symbolic_only hybrid_no_translation hybrid_no_clarification` — within their respective query scopes (Table 11)
- [ ] Execute Phase 3 RAG Triad LLM-as-judge scoring
- [ ] Generate expert evaluation CSVs
- [ ] Generate all thesis figures

---

## Milestone 8: Evaluation Redesign Modifications (Decisions 1–8)

> These changes retrofit the already-implemented Milestones 1–6 to align with the structural redesign captured in `evaluation-redesign-decisions.md`.

### 8a: `data/benchmark-queries.json` — Schema Updates

> **Verified complete** — all items confirmed by direct inspection of the JSON file.

- [x] Convert 6 single-turn ambiguous queries to `multi_turn` (Q003, Q006, Q048, Q063, Q073, Q075): set `"query_type": "multi_turn"`, add `conversation_history` array with the 3-turn clarification exchange, remove top-level `turn3_scripted_response` field (Decision 5 & 6)
- [x] Add Phase 2 fields to all 30 multi-turn queries: `turn5_query`, `turn6_reference_answer`, `gold_chunks_turn6`, `gold_article_refs_turn6` — populate values per the topic assignments in Decision 6 (Decision 3 & 6)
- [x] Update `benchmark_metadata.distribution.by_type`: `single_turn` 76 → **70**, `multi_turn` 24 → **30** (Decision 6)
- [x] Update language distribution counts: EN = 35, FIL = 35, CEB = 30 (Decision 7)
- [x] Update retrieval target distribution counts: symbolic = 25, lexical = 25, dense = 25, hybrid = 25 (Decision 8)

### 8b: `config.py` — Variant Scope Corrections

- [x] Fix stale docstring comment in `get_queries_for_variant()`: `"non_english": Only Filipino and Cebuano queries (50 queries)` → **(65 queries)** (FIL 35 + CEB 30) (Decision 7)
- ~~[ ] Update total-run constant or comment: **695** (was 680)~~ — **N/A**: no total-run constant or comment exists in `config.py`. The "680/695" reference belongs in README.md (covered in 8i below).

### 8c: `collector.py` — Phase 2 Fields in `QueryTrace`

- [x] Add 6 Phase 2 fields to `QueryTrace` dataclass (Decision 3 & 6):
  ```python
  turn5_query: Optional[str]
  turn6_generated_answer: Optional[str]
  turn6_extracted_citations: Optional[List[str]]
  gold_chunks_turn6: Optional[List[str]]
  gold_article_refs_turn6: Optional[List[str]]
  turn6_reference_answer: Optional[str]
  ```
- [x] In `QueryTrace.from_query()`, populate `turn5_query`, `gold_chunks_turn6`, `gold_article_refs_turn6`, and `turn6_reference_answer` from the query JSON at load time alongside the existing gold fields

### 8d: `runner.py` — Multi-Turn Phase 2 Execution & RRF-Correct Multi-K

- [x] Implement Phase 2 execution for multi-turn queries in `full` mode (Decision 3): after Phase 1 (Turn 4) answer is captured, inject the Turn 4 assistant response into the conversation, then send `turn5_query` through `process_message_stream`, and capture Turn 6 outputs into the Phase 2 `QueryTrace` fields
- [x] Ensure all three Table 8 configs (`llm_only`, `stage2_only`, `full_pipeline`) receive full conversation history (Turns 1–5) before generating Turn 6 — configs are distinguished by their retrieval query, not by whether history is provided (Decision 4)
- [x] Skip Phase 2 in `retrieval_only` mode — Table 8 reports answer-quality metrics only; no Phase 2 retrieval pass is needed for Turn 6 (Decision 2). *(Currently implicit — becomes explicit once Phase 2 code is added.)*
- [x] **Replace single-pass-then-slice with separate retrieval calls per K** (RRF constraint): `_run_retrieval_only()` calls retrieval once at `max(top_k)` and stores results for scorers to slice. Under RRF, sub-selecting top-K from a larger pool does **not** reproduce the native top-K rankings. Fix: issue an independent retrieval call for each K value in `--top-k` and store per-K result lists in `QueryTrace` (Decision 8)
- [x] Update `run_validate_multiturn()` docstring: replace "24 multi-turn queries" with **30**; add a printed pass/fail threshold check (≥ 30/30 to proceed) (Decision 6)

### 8e: `scorers/retrieval.py` — Chunk ID Comparison

> **Original item was based on a stale assumption and must not be applied.**
> Inspection confirmed: `gold_chunks` in the JSON are **chunk_id strings** (e.g., `dole_handbook_2023_min_wage_intro_coverage_rates`), not Supabase UUIDs. The collector's `_resolve_chunk_id()` already extracts `metadata.chunk_id` from retrieval results. Replacing `strip().lower()` normalization with UUID equality would break scoring.

- [x] ~~Replace chunk ID path-normalization logic with UUID direct equality~~ — **Superseded**: `gold_chunks` are chunk_id strings, not UUIDs. The current `strip().lower()` normalization in `normalize_chunk_id()` is correct and consistent with `collector._resolve_chunk_id()`. No change required.

### 8f: `scorers/clarification.py` — Demote to Pre-flight Diagnostic

- [ ] Add a module-level constant `IS_THESIS_TABLE = False` with a docstring clarifying that clarification detection P/R is a **pre-flight diagnostic only** — results must not appear in thesis-table output in the raw results CSV (Decision 1)
- [ ] Gate the scorer's output: only emit clarification detection scores when running `--validate clarification`; omit from normal `full`/`retrieval_only` run results

### 8g: `exporters/csv_exporter.py` — Phase 2 Columns

- [ ] Add `system_answer_turn6` and `turn6_reference_answer` columns to the expert evaluation CSV for multi-turn rows (§5.1 update, Decision 3)
- [ ] Ensure Turn 4 `generated_content` populates expert CSV rows for Tables 6, 7, 9, 10; Turn 6 `turn6_generated_answer` populates rows for Table 8 (Decision 3)
- ~~[ ] Update raw results CSV run count annotation from 680 → **695** runs~~ — **N/A**: no such annotation exists in `csv_exporter.py`. Run count is a README concern (covered in 8i below).

### 8h: `exporters/chart_generator.py` — Subset Annotations

> **Both original items are N/A** — the chart generator reads all data dynamically from the results DataFrame; no subset counts or total-run annotations are hardcoded in any chart method. One pre-existing bug was found (covered in 8i).

- ~~[ ] Table 3 heatmap: update per-subset `n` annotation (symbolic=15→25, etc.)~~ — **N/A**: no hardcoded `n` annotations; subset sizes are derived from the data.
- ~~[ ] Ablation heatmap: update total-variant annotation to 695~~ — **N/A**: no hardcoded total-run annotation in the chart.

### 8i: Additional Fixes Found During Audit (Not in Original Checklist)

- [ ] **Variant name inconsistency (functional bug):** `config.py` defines the variant as `hybrid_no_clarification`, but `chart_generator.py` `VARIANT_LABELS` uses the key `"no_clarification"` and `README.md` lists it as `no_clarification`. The chart generator will silently skip traces from this variant. Fix: rename the key in `VARIANT_LABELS` to `"hybrid_no_clarification"` and update `README.md` variant table accordingly.
- [ ] **`README.md` stale references:** Update the following:
  - Line 4 and line 49: "680 total runs" / "Total runs: 680" → **695**
  - Line 45: non-English scope "(50)" → **(65)**
  - Lines 71, 98, 206: remove all "Table 5" references (Table 5 was dropped per Decision 1); update the execution flow diagram and Phase 1c section accordingly
- [ ] **`runner.py` module docstring** (line 5): the `analysis_only` mode description still references "Table 5" — update to reflect that `analysis_only` is now used only for `--validate clarification` pre-flight diagnostics

---

## Execution Cost Summary

| Phase | Mode | Est. Cost |
|---|---|---|
| 0 — Validation | `analysis_only` | < $0.20 |
| 1 — Retrieval (Tables 2–4) | `retrieval_only` | ~$1–2 |
| 2 — Full pipeline (Tables 6–10) | `full` | ~$10–15 |
| 3 — RAG Triad | LLM-as-judge | ~$3–5 |
| **Total** | | **~$14–22** |
