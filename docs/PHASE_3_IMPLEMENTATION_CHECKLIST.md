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

- [x] Verify `benchmark-queries.json` schema: 100 queries, all required fields (`gold_chunks`, `gold_article_refs`, `reference_answer`, `conversation_history` for multi-turn, `expected_clarification` for ambiguous)
- [x] End-to-end dry run: `--smoke` passes on all 5 representative queries
- [ ] Run `--validate all` — both clarification and multi-turn pass
- [ ] Execute Phase 1 retrieval-only runs (Tables 2–4)
- [ ] Execute Phase 1c analysis-only run (Table 5)
- [ ] Review retrieval metrics before proceeding to Phase 2
- [ ] Execute Phase 2 full pipeline runs (Tables 6–10)
- [ ] Execute Phase 3 RAG Triad LLM-as-judge scoring
- [ ] Generate expert evaluation CSVs
- [ ] Generate all thesis figures

---

## Execution Cost Summary

| Phase | Mode | Est. Cost |
|---|---|---|
| 0 — Validation | `analysis_only` | < $0.20 |
| 1 — Retrieval | `retrieval_only` | ~$1–2 |
| 1c — Clarification | `analysis_only` | < $0.10 |
| 2 — Full pipeline | `full` | ~$10–15 |
| 3 — RAG Triad | LLM-as-judge | ~$3–5 |
| **Total** | | **~$15–22** |
