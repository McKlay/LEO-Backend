# Evaluation Design Decisions — Benchmark Redesign

**Date:** April 3–4, 2026  
**Status:** Approved — changes applied to `Evaluation and Benchmarking v2.md`  
**Scope:** Structural fixes to Table 5, Table 7, Table 8, and the multi-turn query design in `benchmark-queries.json`; schema alignment for single-turn ambiguous queries; Table 8 sample size upgrade (n = 24 → 30)

---

## Decision 1: Drop Table 5 (Clarification Detection Accuracy)

**Removed from:** §5.3.2

**Rationale:**  
A standalone detection metric (precision/recall of whether Stage 1 fires its clarification branch) is insufficient as a primary measure because:
- A correctly _detected_ ambiguous query can still produce a poor answer if the clarification question asked is unhelpful.
- A missed detection shows up _directly_ as a lower expert score in Table 7 — the signal is already captured downstream.
- Table 7 (Answer Quality — Ambiguous Subset) provides the end-to-end measurement that subsumes detection accuracy.
 
**What replaces it:**  
§5.3.2 is renamed to "Clarification Impact on Answer Quality (Claim 3)" and explains that clarification is evaluated through Table 7 only. The scoped execution note for the `Hybrid – no clarification` ablation variant (n=30) is retained.

---

## Decision 2: Omit Retrieval Metrics from Table 8 (Multi-Turn Evaluation)

**Rationale:**  
The effect of Stage 1 query consolidation on retrieval quality is already measured at Turn 4 in Tables 2 and 3. Table 8 evaluates Turn 6 answers, where the primary claim is about final answer quality resulting from Stage 1 summarization — not a second retrieval measurement. Adding Recall@K/Hit Rate@K to Table 8 would create measurement overlap without adding new evidence for any of the three research claims.

**Result:**  
Table 8 contains answer quality metrics only: Mean Expert Score (1–4) and % Fully Correct (score = 4).

---

## Decision 3: Two-Phase Structure for Multi-Turn Queries (benchmark-queries.json)

**Background:**  
All 24 multi-turn queries previously followed the same 3-turn clarification template (Turn 1: vague query → Turn 2: clarification question → Turn 3: specific answer), making Table 8 and Table 7 test the same behavior on overlapping queries.

**Resolved structure:**

| Phase | Turns | Purpose | Tables evaluated |
|-------|-------|---------|-----------------|
| Phase 1 | 1–4 | Ambiguous query → clarification exchange → first resolved answer | Tables 2, 3, 4, 6, 7 |
| Phase 2 | 5–6 | Follow-up on a related but distinct labor law topic | Table 8 only |

- **Turn 4** is the first answer after clarification. This is the evaluation point for Table 7 (ambiguous subset answer quality) and for retrieval metrics (Tables 2, 3).
- **Turn 5** is a new, specific (non-ambiguous) follow-up question that introduces a related but distinct topic, grounded in the established Phase 1 context (e.g., if Phase 1 established the worker is in Calabarzon earning ₱400/day, Turn 5 asks "What if I'm transferred to Metro Manila at the same salary?").
- **Turn 6** is the reference answer for Turn 5. This is the evaluation point for Table 8.

**Why Turn 5 must be non-ambiguous:**  
Table 8 tests Stage 1's _summarization_ capability — can it consolidate the full conversation context into a better retrieval query? If Turn 5 were also ambiguous, it would re-test clarification detection (Table 7), not summarization. Turn 5 must be specific so that the only Stage 1 advantage is context consolidation.

---

## Decision 4: Config A and Config B Both Receive Full Conversation History (Table 8)

**Rationale:**  
Conversation history is a general input enrichment available to any dialogue system — it is not a Stage 1-exclusive capability. An LLM chatbot without RAG (Config A) still uses chat history, just as ChatGPT does without a query analysis layer. Withholding history from Config A/B would create an unfair comparison where their disadvantage comes from input deprivation, not from the absence of Stage 1.

**What distinguishes the three configurations for Table 8:**

| Config | History received | Retrieval query | Stage 3 input |
|--------|-----------------|-----------------|---------------|
| **A: LLM-only** | Full (Turns 1–5) | None | History only, no retrieved context |
| **B: Stage 2 only** | Full (Turns 1–5) | Raw Turn 5 text (no Stage 1 summarization) | Retrieved context + history |
| **C: Full Pipeline** | Full (Turns 1–5) | Stage 1 consolidated query from all prior turns | Enriched retrieved context + history |

The B→C delta therefore isolates the effect of Stage 1's history summarization on retrieval and generation quality.

---

## Decision 5: Structured `conversation_history` for Single-Turn Ambiguous Queries

**Scope:** 6 queries — Q003, Q006, Q048, Q063, Q073, Q075

**Background:**  
After Decision 1 dropped Table 5 (clarification detection accuracy), the evaluation target for all ambiguous queries shifted to Turn 4 — the final answer produced after the clarification exchange. The 6 single-turn ambiguous queries previously stored Turn 2 and Turn 3 as flat top-level fields (`expected_clarification` and `turn3_scripted_response`). The multi-turn ambiguous queries had already formalised this same exchange inside a `conversation_history` array. The schema was therefore inconsistent: single-turn ambiguous queries lacked the structured turn history that any execution engine needs to produce a Turn 4 answer.

**Resolution:**  
For all 6 single-turn ambiguous queries, `conversation_history` is added containing the full 3-turn clarification exchange:

```json
"conversation_history": [
  { "role": "user",      "text": "<query_text>"             },
  { "role": "assistant", "text": "<expected_clarification>" },
  { "role": "user",      "text": "<scripted Turn 3 reply>"  }
]
```

- `turn3_scripted_response` is **removed** from the top level (its content is now the third entry in `conversation_history`).
- `expected_clarification` is **retained** as a top-level reference field — it records the ideal Turn 2 question for documentation and potential qualitative analysis.
- No change to `gold_chunks`, `gold_article_refs`, or `reference_answer`; these still target the Turn 4 answer.

**Why this is necessary:**  
Since evaluation is on Turn 4 (not clarification quality), the system must receive Turns 1–3 as context before generating Turn 4. Having them inside `conversation_history` is consistent with the multi-turn query format and removes the need for any special-case handling in the evaluation harness for this query subset.

**Single-turn ambiguous queries do not receive Turn 5/6 extensions.** They are evaluated only in Table 7. *(Superseded by Decision 6 — see below.)*

---

## Decision 6: Convert 6 Single-Turn Ambiguous Queries to Multi-Turn (Table 8 n = 24 → 30)

**Scope:** 6 queries — Q003, Q006, Q048, Q063, Q073, Q075

**Background:**  
After the two-phase structure was formalised in Decision 3, Table 8 (Multi-Turn Answer Quality) operated on n = 24 multi-turn queries. A sample of 24 falls below the common rule-of-thumb minimum of n ≥ 25–30 for applying parametric statistical methods (e.g., t-tests, Cohen's κ confidence intervals) with adequate power. Table 7 already had n = 30. This asymmetry weakened the statistical equivalence of the two primary answer-quality tables.

**Resolution:**  
The 6 formerly `single_turn` ambiguous queries are promoted to `multi_turn`. Each receives the four Phase 2 fields:

```json
"turn5_query": "...",
"turn6_reference_answer": "...",
"gold_chunks_turn6": ["..."],
"gold_article_refs_turn6": ["..."]
```

Turn 5 topics were designed so that each follow-up question is specific (non-ambiguous) and grounded in the context established by Phase 1, following the same constraint imposed on the original 24 multi-turn queries (Decision 3): Turn 5 must avoid re-testing clarification detection so that Table 8 isolates Stage 1's history summarization capability.

The Phase 2 topics assigned to each converted query:

| Query | Phase 1 topic (Turn 3 context) | Turn 5 topic |
|-------|-------------------------------|-------------|
| Q003 | NCR min. wage — non-agricultural | Money claims prescriptive period (Art. 306) |
| Q006 | NCR min. wage — non-agricultural | Holiday pay for working on a regular holiday (Art. 94) |
| Q048 | Disease-related termination risk | SSS sickness benefit while still employed (RA 11199 Sec. 14) |
| Q063 | SSS maternity benefit | Maternity leave duration and pay source (RA 11210 Sec. 6) |
| Q073 | ECP claim for work injury (employer view) | SSS disability benefit vs. ECP — parallel claims (RA 11199 Sec. 13-B) |
| Q075 | Work accident — ECP/SSS benefits | Authorized cause termination due to disability + separation pay (Art. 299) |

The `distribution.by_type` in `benchmark_metadata` is updated:
- `single_turn`: 76 → **70**
- `multi_turn`: 24 → **30**

**Effect on evaluations:**
- **Table 7** (Claim 3 — clarification impact): unchanged; n = 30 (all 30 ambiguous queries rated at Turn 4).
- **Table 8** (multi-turn summarization): n = 24 → **n = 30**.

Both Table 7 and Table 8 now evaluate the same 30-query population — at Turn 4 and Turn 6 respectively — providing symmetric sample sizes for the two primary answer-quality tables.

**Supersedes:** The final note in Decision 5 stating "Single-turn ambiguous queries do not receive Turn 5/6 extensions."

---

## Required Changes to `benchmark-queries.json`

### Schema addition (all 30 multi-turn queries)

Each of the 30 queries with `"query_type": "multi_turn"` must have the following four fields added at the same level as `conversation_history`:

```json
"turn5_query": "...",
"turn6_reference_answer": "...",
"gold_chunks_turn6": ["..."],
"gold_article_refs_turn6": ["..."]
```

### Field definitions

| Field | Type | Description |
|-------|------|-------------|
| `turn5_query` | string | The user's follow-up question in Turn 5. Must be specific (non-ambiguous) and introduce a related but distinct labor law topic grounded in Phase 1 context. |
| `turn6_reference_answer` | string | The canonical expected answer for Turn 5. Evaluated in Table 8. |
| `gold_chunks_turn6` | string[] | The knowledge base chunk(s) that contain the authoritative answer to `turn5_query`. |
| `gold_article_refs_turn6` | string[] | Canonical statute citations for `turn5_query` (e.g., `"Wage Order NCR-24"`). |

### Example — Q007 extended

```json
{
  "query_id": "Q007",
  "query_text": "Kulang ang sahod ko.",
  "language": "fil",
  "query_type": "multi_turn",
  "is_ambiguous": true,
  "topic": "wages_minimum_wage",
  "retrieval_target": "dense",
  "expected_clarification": "Para matulungan kita, maaari mo bang sabihin kung saan ka nagtatrabaho (region), kung anong trabaho mo, at kung magkano ang binabayad sa iyo?",
  "conversation_history": [
    { "role": "user",      "text": "Kulang ang sahod ko." },
    { "role": "assistant", "text": "Para matulungan kita, maaari mo bang sabihin kung saan ka nagtatrabaho (region), kung anong trabaho mo, at kung magkano ang binabayad sa iyo?" },
    { "role": "user",      "text": "Factory worker ako sa Calabarzon. Ang sahod ko ay 400 pesos lang bawat araw." }
  ],
  "gold_chunks": ["DOLE-Handbook/02-minimum-wage-coverage-rates.md"],
  "gold_article_refs": ["RA 6727", "Wage Order Calabarzon"],
  "reference_answer": "Ayon sa DOLE Handbook, ang minimum wage sa Calabarzon para sa non-agricultural workers ay mas mataas sa ₱400. Kung kulang ang sahod mo, maaari kang mag-file ng complaint sa DOLE Regional Office.",
  "notes": "Multi-turn + ambiguous + Filipino. Phase 1 evaluation (Turn 4). Tests: (1) clarification detection, (2) translation pivot.",

  "turn5_query": "Paano kung ililipat ng employer ko ang trabaho ko sa Metro Manila, pero 400 pesos pa rin ang sahod?",
  "turn6_reference_answer": "Kung inilipat ang iyong trabaho sa NCR, nalalapat na ang minimum wage ng NCR na itinakda ng RTWPB (mas mataas kaysa sa Calabarzon). Ang iyong employer ay obligadong ayusin ang iyong sahod ayon sa NCR wage order. Kung hindi nila gagawin ito, maaari kang magreklamo sa DOLE-NCR.",
  "gold_chunks_turn6": ["DOLE-Handbook/02-minimum-wage-coverage-rates.md"],
  "gold_article_refs_turn6": ["Wage Order NCR-24", "RA 6727"]
}
```

### Update to `labeling_notes` in `benchmark_metadata`

Change from:
```
"For multi-turn queries, conversation_history records the full dialog; for ambiguous queries, expected_clarification gives the system's ideal follow-up question."
```

Change to:
```
"For multi-turn queries, conversation_history records the Phase 1 dialog (Turns 1–3); turn5_query and turn6_reference_answer extend the conversation into Phase 2 for multi-turn summarization evaluation. gold_chunks and gold_article_refs target Turn 4 (Tables 2, 3, 7); gold_chunks_turn6 and gold_article_refs_turn6 target Turn 6 (Table 8). For ambiguous queries, expected_clarification gives the system's ideal Turn 2 follow-up question."
```

### Schema change for the 6 formerly single-turn ambiguous queries (Decisions 5 & 6)

Per **Decision 5**, these 6 queries (Q003, Q006, Q048, Q063, Q073, Q075) received a `conversation_history` array containing the full Turn 1–3 clarification exchange; `turn3_scripted_response` was removed from the top level; `expected_clarification` was retained as a top-level reference field.

Per **Decision 6**, these 6 queries are additionally promoted to `"query_type": "multi_turn"` and each receives the four Phase 2 fields (`turn5_query`, `turn6_reference_answer`, `gold_chunks_turn6`, `gold_article_refs_turn6`), following the same schema as the original 24 multi-turn queries.

---

## Required Changes to `Evaluation and Benchmarking v2.md`

| Section | Change |
|---------|--------|
| §5.1.1 | Add two-phase structure description for multi-turn queries |
| §5.1.2 | Add note that single-turn ambiguous queries now carry `conversation_history` (Turns 1–3) and are evaluated at Turn 4 |
| §5.3.2 | Rename, remove Table 5, rewrite to single-measurement clarification evaluation |
| §5.4.1 (Table 7) | Add note clarifying that Turn 4 is the rated answer for both multi-turn and single-turn ambiguous queries in this subset |
| §5.4.2 | Rewrite Config A/B/C descriptions; clarify Turn 6 is the evaluation point for Table 8 |

---

## Impact on Evaluation Counts (no change to total effort)

The overall manual evaluation effort remains **600 individual ratings** (3 configurations × 100 queries × 2 experts). Table 8 evaluates Turn 6 answers for all 30 multi-turn queries, which are a subset of the 100 already counted. No additional queries are added to the benchmark — the 6 single-turn ambiguous queries are reclassified as multi-turn and extended with Turn 5/6 Phase 2 fields (Decision 6), bringing Table 8 to n = 30 and aligning its sample size with Table 7.

---

## Decision 7: Language Distribution Rebalance (50/30/20 → 35/35/30)

**Scope:** `benchmark-queries.json` single-turn queries only (n = 70). All 30 multi-turn/ambiguous queries are unchanged.

**Rationale:** Under the original 50/30/20 split, Cebuano had n = 20 — below the n ≥ 25–30 rule-of-thumb for parametric methods (t-tests, Cohen's κ confidence intervals). Rebalancing ensures all three language groups meet the statistical minimum required for per-language subgroup analysis.

**Method:** Translated 15 single-turn English queries: 5 → Filipino, 10 → Cebuano. Only the `query_text`, `language`, `reference_answer`, and `notes` fields were modified. The `retrieval_target`, `gold_chunks`, and `gold_article_refs` fields are preserved unchanged. Symbolic queries (those containing explicit article citations in the query text) were excluded from conversion to preserve symbolic retriever routing integrity.

**Queries converted → Filipino (5):** Q001, Q017, Q036, Q041, Q069

**Queries converted → Cebuano (10):** Q008, Q009, Q023, Q030, Q051, Q053, Q057, Q061, Q077, Q082

**Resulting single-turn distribution:** EN: 16, FIL: 28, CEB: 26

**Resulting overall distribution:** EN: 35, FIL: 35, CEB: 30

**`benchmark_metadata` update:** `distribution.by_language` updated to `"en": 35, "fil": 35, "ceb": 30`.

---

## Decision 8: Retrieval Target Distribution Rebalance (15/23/27/35 → 25/25/25/25)

**Date:** 2025-07  
**Scope:** `benchmark-queries.json` single-turn queries only (n = 70). All 30 multi-turn/ambiguous queries unchanged.

**Rationale:** The original `retrieval_target` distribution (symbolic: 15, lexical: 23, dense: 27, hybrid: 35) left the symbolic subset below the n ≥ 25 minimum required for per-strategy subgroup analysis using parametric methods (t-tests, Cohen's κ confidence intervals). Equal 25-each counts ensure all four retrieval strategy subsets are adequately powered.

**Method:** Changed `retrieval_target` for 12 single-turn queries:

- **8 hybrid → symbolic** (Q064, Q065, Q070, Q072, Q074, Q083, Q088, Q093): Explicit statute/rule citations added to `query_text` to reflect the symbolic character of each query.
- **2 hybrid → lexical** (Q097, Q099): Queries already had strong domain keywords suited for BM25; no text changes required.
- **2 dense → symbolic** (Q089, Q095): NLRC Rule V and SEnA Rule IV citations added to `query_text`.

`notes` fields for all 30 multi-turn queries were also updated to contain an explicit "Retrieval target: [type] — [reason]" statement. Short single-turn `query_text` values were lengthened with realistic personal context for query realism.

**Resulting distribution:** symbolic: 25, lexical: 25, dense: 25, hybrid: 25 (verified).

**`benchmark_metadata` update:** `distribution.by_retrieval_target` updated to `"symbolic": 25, "lexical": 25, "dense": 25, "hybrid": 25`.
