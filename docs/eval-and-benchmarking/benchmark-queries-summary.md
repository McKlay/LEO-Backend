# Benchmark Query Set — Summary & Design Rationale

> **File:** `benchmark-queries.json` (100 queries, machine-readable)  
> **Purpose:** Canonical evaluation dataset for the Three-Stage Hybrid RAG pipeline on Philippine labor-law QA.

---

## Distribution Summary

| Dimension | Category | Count | % |
|-----------|----------|------:|----:|
| **Language** | English | 35 | 35% |
| | Filipino | 35 | 35% |
| | Cebuano | 30 | 30% |
| **Query Type** | Single-turn | 70 | 70% |
| | Multi-turn (dialog) | 30 | 30% |
| **Ambiguity** | Clear (answerable) | 70 | 70% |
| | Ambiguous (needs clarification) | 30 | 30% |
| **Retrieval Target** | Symbolic (article lookup) | 25 | 25% |
| | Lexical (BM25/keyword) | 25 | 25% |
| | Dense (semantic) | 25 | 25% |
| | Hybrid (multi-strategy) | 25 | 25% |

---

## Topic Coverage (19 Categories)

| # | Topic | Queries | Primary Corpus Sources |
|---|-------|--------:|------------------------|
| 1 | Wages / Minimum wage | 10 | PD-442 (Arts. 97–129), DOLE-Handbook (02–04) |
| 2 | Hours of work / Overtime / NSD | 6 | PD-442 (Arts. 82–90), DOLE-Handbook (06–07) |
| 3 | Holiday / Rest day / Premium pay | 6 | PD-442 (Arts. 91–96), DOLE-Handbook (05–06) |
| 4 | Leave benefits | 7 | DOLE-Handbook (09–10), RA 11210, RA 8187, RA 9262 |
| 5 | 13th month pay | 6 | PD-851 (all chunks), DOLE-Handbook (11) |
| 6 | Separation pay | 5 | PD-442 (Art. 298–299), DO-147-15 (05), Handbook (12) |
| 7 | Retirement pay | 4 | PD-442 (Art. 302), DOLE-Handbook (13) |
| 8 | Termination / Due process | 12 | DO-147-15 (02–06), PD-442 (Art. 278–286) |
| 9 | Kasambahay (domestic workers) | 6 | RA-10361 (all chunks), DOLE-Handbook (04) |
| 10 | SSS benefits | 6 | RA-11199 (06–08), DOLE-Handbook (16) |
| 11 | PhilHealth / Pag-IBIG | 4 | DOLE-Handbook (15, 17) |
| 12 | Employees' Compensation | 4 | PD-442 (Arts. 166–204), DOLE-Handbook (14) |
| 13 | Occupational Safety & Health | 5 | RA-11058 (04–09) |
| 14 | Labor relations / Unions | 5 | PD-442 (Arts. 211–277) |
| 15 | NLRC procedure | 5 | NLRC-Rules (03–12) |
| 16 | SEnA conciliation | 4 | SEnA (01–05) |
| 17 | COVID-19 protocols | 2 | DOLE-Covid-Protocols (01–03) |
| 18 | Contractor liability | 2 | PD-442 (Arts. 106–111) |
| 19 | Recruitment / Overseas employment | 1 | PD-442 (Arts. 40–42) |

---

## Design Rationale — Mapping to Research Claims

### Claim 1: Hybrid retrieval > single retriever

Each query is tagged with a `retrieval_target` indicating which retrieval strategy is expected to be most effective:

- **Symbolic** (25 queries): Include explicit article/section references (e.g., "What does Article 94 say…"). Symbolic lookup should score well here; dense/lexical alone may miss exact references.
- **Lexical** (25 queries): Keyword-rich factoid questions (e.g., "What are the just causes for termination…"). BM25 should excel; dense may return topically related but wrong provisions.
- **Dense** (25 queries): Paraphrased/colloquial queries (e.g., "Can my boss fire me for being late?"). Semantic search should outperform keyword matching.
- **Hybrid** (25 queries): Complex or cross-source queries needing multiple strategies working together.

**Evaluation protocol:** Run each query against dense-only, lexical-only, symbolic-only, and full hybrid. Compare Recall@K and MRR across all 100 queries, with breakdown by `retrieval_target` to show where each strategy wins or fails.

### Claim 2: Translation pivot improves retrieval for Filipino/Cebuano

- 35 Filipino queries and 30 Cebuano queries are included
- All corpus chunks are in English, so non-English queries *must* be translated for effective retrieval
- **Ablation:** Disable translation (search in original Filipino/Cebuano) vs. translate-to-English pivot
- **Expected result:** Dramatic recall drop for non-English queries without translation (consistent with §5.2 of the Evaluation document: +18% Hit Rate@5 improvement with translation)

### Claim 3: Clarification handling reduces errors under ambiguity

- 30 queries (30%) are intentionally ambiguous
- All 30 ambiguous queries follow the two-phase multi-turn structure: Phase 1 (Turns 1–3) is the clarification exchange leading to a Turn 4 answer evaluated in Table 7; Phase 2 (Turn 5) is a specific, non-ambiguous follow-up with a Turn 6 reference answer evaluated in Table 8
- **Ablation:** Disable clarification module (force system to answer ambiguous queries directly)
- **Expected result:** Accuracy drops significantly on ambiguous queries without clarification (consistent with §5.4: 85% → 55%)

### Multi-turn evaluation (30 queries)

- 30 queries include `conversation_history` with multiple exchanges
- All 30 are structured in two phases: Phase 1 (Turns 1–3 clarification exchange → Turn 4 first resolved answer) and Phase 2 (Turn 5 specific follow-up → Turn 6 reference answer)
- Tests Stage 1's ability to: (1) conduct an effective clarification exchange to improve Turn 4 answer quality (Table 7), and (2) consolidate the full conversation history into an enriched retrieval query for the Phase 2 follow-up (Table 8)

---

## Schema Reference

Each query object contains:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query_id` | string | ✓ | Unique identifier (Q001–Q100) |
| `query_text` | string | ✓ | The user's query text |
| `language` | string | ✓ | `en`, `fil`, or `ceb` |
| `query_type` | string | ✓ | `single_turn` or `multi_turn` |
| `is_ambiguous` | boolean | ✓ | Whether query needs clarification |
| `topic` | string | ✓ | Topic category (19 values) |
| `retrieval_target` | string | ✓ | `symbolic`, `lexical`, `dense`, or `hybrid` |
| `gold_chunks` | string[] | ✓ | Expected chunk files from `kb/chunks/` |
| `gold_article_refs` | string[] | ✓ | Canonical legal citations |
| `reference_answer` | string | ✓ | Gold-standard expected answer |
| `notes` | string | ✓ | Evaluation notes |
| `expected_clarification` | string | if ambiguous | System's ideal clarification question |
| `conversation_history` | object[] | if multi-turn | Array of `{role, text}` exchanges (Turns 1–3) |
| `turn5_query` | string | if multi-turn | Phase 2 follow-up question (specific, non-ambiguous) |
| `turn6_reference_answer` | string | if multi-turn | Canonical reference answer for Turn 5; evaluated in Table 8 |
| `gold_chunks_turn6` | string[] | if multi-turn | Gold-standard chunk IDs for the Turn 5 answer |
| `gold_article_refs_turn6` | string[] | if multi-turn | Canonical statute citations for the Turn 5 answer |

---

## Usage in Experiments

```python
import json

with open("benchmark-queries.json", "r") as f:
    benchmark = json.load(f)

# Run all queries
for query in benchmark["queries"]:
    result = pipeline.run(
        query_text=query["query_text"],
        language=query["language"],
        conversation_history=query.get("conversation_history", [])
    )
    
    # Evaluate retrieval
    retrieved_chunks = result.retrieved_chunks
    recall_at_k = compute_recall(retrieved_chunks, query["gold_chunks"], k=5)
    
    # Evaluate answer
    answer_score = compute_f1(result.answer, query["reference_answer"])
    citation_fidelity = check_citations(result.answer, query["gold_article_refs"])
    
    # Evaluate clarification (if ambiguous)
    if query["is_ambiguous"]:
        clarification_quality = evaluate_clarification(
            result.clarification_question,
            query["expected_clarification"]
        )
```

---

## Corpus Coverage Validation

All 10 source document folders in `kb/chunks/` are referenced by at least one query:

| Document | Chunks | Queries Referencing |
|----------|-------:|--------------------:|
| PD-No-442 (Labor Code) | 65 | 48 |
| PD-No-851 (13th Month) | 5 | 6 |
| RA-No-10361 (Kasambahay) | 10 | 6 |
| RA-No-11058 (OSH) | 11 | 5 |
| RA-No-11199 (SSS) | 14 | 6 |
| DOLE-Dep-Order-147-15 | 7 | 12 |
| DOLE-Handbook | 18 | 38 |
| DOLE-Covid-Protocols | 3 | 2 |
| NLRC-Rules | 22 | 5 |
| SEnA | 6 | 5 |
