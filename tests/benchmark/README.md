# LEO Benchmark — Automated Evaluation Framework

Standalone benchmark suite for the LEO Philippine Labor Law RAG pipeline.
Evaluates 8 pipeline variants across 100 queries (695 total runs) and produces
all retrieval metrics, answer-quality scores, and thesis figures documented in
§4.5 of the methodology chapter.

> **No HTTP server required.** The runner imports the pipeline in-process via
> `app.containers` — identical code paths as production, zero network overhead.

---

## Directory Structure

```
tests/benchmark/
├── runner.py            # Orchestrator + CLI entry point
├── config.py            # 8 VariantConfig definitions + apply_variant / reset_singletons
├── collector.py         # QueryTrace dataclass + ResultCollector (SSE → trace)
├── scorers/
│   ├── retrieval.py     # Recall@K, Hit Rate@K, MRR
│   ├── answer_quality.py# Token F1, ROUGE-L, Exact Match
│   ├── citation.py      # Citation extraction, precision / recall
│   ├── clarification.py # Clarification detection TP / FP / FN
│   └── rag_triad.py     # GPT-4.1 LLM-as-judge (Context Relevance, Groundedness, Answer Relevance)
├── exporters/
│   ├── csv_exporter.py  # Raw results CSV + blinded expert evaluation CSV
│   └── chart_generator.py  # 8 thesis figures (PDF + PNG)
├── data/
│   └── benchmark-queries.json   # 100 queries with gold labels
└── results/             # gitignored — runner output lives here
```

---

## Pipeline Variants

| # | Name | Retrieval | Query Analysis | Translation | Clarification | Scope |
|---|------|-----------|----------------|-------------|---------------|-------|
| 1 | `full_pipeline` | hybrid | ✓ | ✓ | ✓ | all (100) |
| 2 | `stage2_only` | hybrid | ✗ | ✗ | ✗ | all (100) |
| 3 | `dense_only` | dense | ✓ | ✓ | ✓ | all (100) |
| 4 | `lexical_only` | lexical | ✓ | ✓ | ✓ | all (100) |
| 5 | `symbolic_only` | symbolic | ✓ | ✓ | ✓ | all (100) |
| 6 | `hybrid_no_translation` | hybrid | ✓ | ✗ | ✓ | non-English (65) |
| 7 | `hybrid_no_clarification` | hybrid | ✓ | ✓ | ✗ | ambiguous (30) |
| 8 | `llm_only` | none | ✗ | ✗ | ✗ | all (100) |

**Total runs: 695**

---

## Quick Start

```bash
# Install benchmark dependencies (once)
pip install rouge-score matplotlib seaborn pandas

# Validate before spending API budget (~$0.10, GPT-4o-mini only)
python -m tests.benchmark.runner --validate all --sample-size 1
python -m tests.benchmark.runner --smoke

# Targeted smoke: inspect a single query's JSON output (cheapest debug path)
python -m tests.benchmark.runner --smoke --query-ids Q005
```

---

## Execution Flow

```mermaid
flowchart LR
    A[--validate all\n~$0.10] --> B[--mode retrieval_only\nTables 2–4\n~$1–2]
    B --> C[--mode full\nTables 6–10\n~$10–15]
    C --> D[rag_triad scorer\n~$3–5]
    D --> E[csv_exporter\nchart_generator]
```

### Phase 0 — Validation

```bash
# Step 1: cheap logic check (GPT-4o-mini only, ~$0.10)
python -m tests.benchmark.runner --validate all --sample-size 1

# Step 2: full-pipeline sanity check (4 representative queries)
python -m tests.benchmark.runner --smoke

# Step 2 (targeted): inspect a specific query before committing to a full smoke run
python -m tests.benchmark.runner --smoke --query-ids Q005
```

### Phase 1 — Retrieval Evaluation (Tables 2–4)

`retrieval_only` mode skips generation entirely — cost is GPT-4o-mini for query analysis only (~$0.001 per query). Always dry-run one query per scenario first.

#### Step 1: Dry Run (2 commands, ~$0.03 total)

Each variant only accepts queries within its scope. Using an out-of-scope query ID silently produces 0 results for that variant.

> **Note:** `hybrid_no_clarification` is **not** part of Phase 1 — clarification is evaluated in Phase 2 full mode on `turn4_response` at K=5 only; it produces no retrieval metrics.

| Scenario | Variants | Scope constraint | Dry-run query ID |
|----------|----------|-----------------|------------------|
| Tables 2–3 (strategy) | `full_pipeline dense_only lexical_only symbolic_only` | any | `Q002` — EN, single-turn, clear |
| Table 4 (translation) | `full_pipeline hybrid_no_translation` | **FIL or CEB only** | `Q001` — FIL, single-turn |

```bash
# Scenario A — strategy comparison (4 variants × 1 query × K = 3, 5, 10)
python -m tests.benchmark.runner --mode retrieval_only --top-k 3 5 10 \
  --variant full_pipeline dense_only lexical_only symbolic_only \
  --query-ids Q002 --output-dir tests/benchmark/results/dry_run_phase1

# Scenario B — translation ablation (2 variants × 1 non-English query × K = 5)
# ⚠ Must be FIL/CEB — an EN query ID yields 0 results for hybrid_no_translation
python -m tests.benchmark.runner --mode retrieval_only --top-k 5 \
  --variant full_pipeline hybrid_no_translation \
  --query-ids Q001 --output-dir tests/benchmark/results/dry_run_phase1
```

After each command, check `tests/benchmark/results/dry_run_phase1/partial/` for the output JSON. Verify before proceeding:
- `retrieved_chunk_ids` is a non-empty list
- `scores` contains `recall_at_5` or similar retrieval metrics
- No `error` field present

#### Step 2: Probe Run (incremental, one variant at a time)

Run variants sequentially into **one shared folder**, always with `--top-k 3 5 10` so K-values are complete from the start. Inspect scores after each variant before continuing. Use `--resume` from the second command onward — the manifest now accumulates across sessions.

```bash
# 1. dense_only — evaluate first (100 queries × K = 3, 5, 10)
python -m tests.benchmark.runner --mode retrieval_only --top-k 3 5 10 \
  --variant dense_only --output-dir tests/benchmark/results/phase1_full

# Inspect results/phase1_full/dense_only_results.json → scores look OK? Continue:

# 2. symbolic_only
python -m tests.benchmark.runner --mode retrieval_only --top-k 3 5 10 \
  --variant symbolic_only --output-dir tests/benchmark/results/phase1_full --resume

# 3. lexical_only
python -m tests.benchmark.runner --mode retrieval_only --top-k 3 5 10 \
  --variant lexical_only --output-dir tests/benchmark/results/phase1_full --resume

# 4. full_pipeline
python -m tests.benchmark.runner --mode retrieval_only --top-k 3 5 10 \
  --variant full_pipeline --output-dir tests/benchmark/results/phase1_full --resume

# 5. hybrid_no_translation — K = 5 only, non-English scope (65 queries)
python -m tests.benchmark.runner --mode retrieval_only --top-k 5 \
  --variant hybrid_no_translation --output-dir tests/benchmark/results/phase1_full --resume
```

> Each session resumes into the same folder. The manifest accumulates all variants and preserves `started_at` across sessions. If a session is interrupted mid-variant, re-run the same command with `--resume` — completed queries are skipped automatically.

#### Step 3: Full Run

Alternative to Step 2 if you prefer running all variants in one shot without pausing to evaluate:

```bash
# Tables 2–3: strategy comparison (4 variants × 100 queries × K = 3, 5, 10)
python -m tests.benchmark.runner --mode retrieval_only --top-k 3 5 10 \
  --variant full_pipeline dense_only lexical_only symbolic_only \
  --output-dir tests/benchmark/results/phase1_full

# Table 4: translation ablation (2 variants × 65 non-English queries × K = 5)
python -m tests.benchmark.runner --mode retrieval_only --top-k 5 \
  --variant hybrid_no_translation --output-dir tests/benchmark/results/phase1_full --resume
```

> `full_pipeline` is already present from the first command; `--resume` skips its completed queries when the second command runs.

### Phase 2 — Full Pipeline (Tables 6–10)

> **Note:** `hybrid_no_clarification` is evaluated here too (Table 9, clarification ablation) on the 30 ambiguous multi-turn queries. Run it after `full_pipeline` is confirmed.

#### Probe Run (recommended — one variant at a time)

```bash
# 0. Smoke test — validate all 3 core variants on one multi-turn query (~$0.05)
python -m tests.benchmark.runner --smoke-phase2 \
  --query-ids Q006 --output-dir tests/benchmark/results/probe_phase2

# 1. llm_only — cheapest; no retrieval, no analysis (100 queries)
python -m tests.benchmark.runner --mode full \
  --variant llm_only --output-dir tests/benchmark/results/phase2_full --resume --api-delay-ms 5000 2>&1

# Inspect phase2_full/llm_only_results.json → scores look OK? Continue:

# 2. stage2_only — adds hybrid retrieval, no Stage 1 per-query analysis (100 queries)
python -m tests.benchmark.runner --mode full \
  --variant stage2_only --output-dir tests/benchmark/results/phase2_full --resume --api-delay-ms 15000

# 3. full_pipeline — most expensive; all stages including GPT-4o-mini analysis (100 queries)
python -m tests.benchmark.runner --mode full \
  --variant full_pipeline --output-dir tests/benchmark/results/phase2_full --resume --api-delay-ms 30000

# 4. hybrid_no_clarification — Table 11 clarification ablation; ambiguous-only scope (30 queries)
python -m tests.benchmark.runner --mode full \
  --variant hybrid_no_clarification --output-dir tests/benchmark/results/phase2_full --resume --api-delay-ms 15000
```

> Each command resumes into the same folder. Use `--resume` from command 2 onward.
> If a session is interrupted mid-variant, re-run the same command with `--resume`.

#### Full Run (one shot, no intermediate inspection)

```bash
# Tables 6–9: all Phase 2 variants in one shot
python -m tests.benchmark.runner --mode full \
  --variant llm_only stage2_only full_pipeline hybrid_no_clarification \
  --output-dir tests/benchmark/results/phase2_full
```

### Phase 3 — RAG Triad Scoring

```bash
python -m tests.benchmark.scorers.rag_triad \
  --input tests/benchmark/results/phase2_full \
  --output tests/benchmark/results/phase3_full/rag_triad \
  --concurrency 5
```

### Export Results

```bash
# Raw CSV + blinded expert evaluation CSV + multi-turn conversation history
python -m tests.benchmark.exporters.csv_exporter \
  --input tests/benchmark/results/phase2_full \
  --output tests/benchmark/results/exports \
  --expert-blind --multiturn

# All 8 thesis figures
python -m tests.benchmark.exporters.chart_generator \
  --input tests/benchmark/results/phase2_full \
  --output tests/benchmark/results/figures
```

---

## CLI Reference

### `runner.py`

| Argument | Default | Description |
|----------|---------|-------------|
| `--mode` | `full` | `analysis_only` · `retrieval_only` · `full` |
| `--variant` | *(required)* | One or more variant names |
| `--top-k` | `5` | K values for retrieval metrics (e.g. `3 5 10`) |
| `--query-ids` | all | Restrict to specific query IDs (e.g. `Q007 Q015`); applies to all modes including `--smoke` |
| `--output-dir` | `results/run_<ts>` | Output directory |
| `--resume` | off | Skip already-completed query–variant pairs |
| `--smoke` | — | Run 4 representative queries (EN/FIL/CEB/multi-turn) as a full-pipeline sanity check; combine with `--query-ids` to run a single query instead |
| `--smoke-phase2` | — | Run all 3 Phase 2 variants (`llm_only`, `stage2_only`, `full_pipeline`) on one multi-turn query and verify turn routing, prior-turn injection, turn4/turn6 population, and scores |
| `--validate` | — | `clarification` · `multiturn` · `all` |
| `--log-level` | `INFO` | `DEBUG` · `INFO` · `WARNING` |
| `--log-file` | — | Tee logs to file |
| `--log-per-variant` | off | Split logs into per-variant files |
| `--quiet` | off | Suppress console output |
| `--api-delay-ms` | `200` | Delay between OpenAI API calls |

### `csv_exporter.py`

| Argument | Description |
|----------|-------------|
| `--input` | Run output directory |
| `--output` | Destination for CSV files |
| `--expert-blind` | Write blinded expert CSV + mapping JSON |
| `--multiturn` | Write multi-turn conversation history CSV |
| `--seed` | RNG seed for blinding (default: 42) |

### `chart_generator.py`

| Argument | Description |
|----------|-------------|
| `--input` | Run output directory |
| `--output` | Destination for figure files |

---

## Automated Metrics

| Scorer | Metrics |
|--------|---------|
| `retrieval.py` | Recall@3/5/10, Hit Rate@3/5/10, MRR |
| `answer_quality.py` | Token F1, ROUGE-L, Exact Match |
| `citation.py` | Citation Precision, Recall, F1 |
| `clarification.py` | Detection Precision, Recall, F1 (TP/FP/FN) |
| `rag_triad.py` | Context Relevance, Groundedness, Answer Relevance (1–5) |

Metric scores are written back into each trace's `scores` dict and included in the raw results CSV.

---

## Resume Support

Every query–variant pair is written to `results/<run>/partial/<query_id>__<variant>.json`
immediately after completion. Interrupted runs can be resumed without re-processing
completed pairs:

```bash
python -m tests.benchmark.runner --mode full --variant full_pipeline \
  --resume --output-dir results/run_001
```

---

## Estimated Cost

| Phase | Mode | Est. Cost |
|-------|------|-----------|
| Validation | `analysis_only` | < $0.20 |
| Retrieval (Tables 2–4) | `retrieval_only` | ~$1–2 |
| Full pipeline (Tables 6–10) | `full` | ~$10–15 |
| RAG Triad | LLM-as-judge | ~$3–5 |
| **Total** | | **~$15–22** |
