# Phase 1 Analysis: Why Hybrid Cannot Surpass Dense-Only

**Date:** April 12, 2026 | **Context:** Post-HPT Round 3 weights (dense=1.0, lexical=0.75, symbolic=0.10)

---

## 1. The Problem

| Metric | Dense-only | Full Pipeline (Hybrid) | Delta |
|--------|-----------|----------------------|-------|
| HR@5 | **0.980** | **0.980** | 0.000 |
| Recall@5 | 0.855 | **0.866** | +0.011 |
| MRR@5 | **0.848** | 0.787 | **-0.061** |
| Rank-1 accuracy | **76/100** | 65/100 | **-11** |

Hybrid matches dense on hit rate and slightly wins on recall (+1.1pp), but **loses 6.1pp on MRR** and places gold at rank 1 **eleven fewer times**. RRF fusion consistently pushes gold chunks down in the ranking.

---

## 2. Root Cause Analysis

### 2.1 The MRR Degradation Mechanism (Primary Cause)

**26 of 100 queries** suffer MRR degradation in hybrid vs. dense. Only **13 queries** see MRR improvement. The net balance:

| Direction | Queries | Total MRR Delta | Avg Delta per Query |
|-----------|---------|----------------|-------------------|
| Degraded (dense > pipeline) | 26 | -13.40 | -0.515 |
| Improved (pipeline > dense) | 13 | +7.33 | +0.564 |
| Tied | 61 | 0 | 0 |
| **Net** | | **-6.07** | **-0.061/query** |

The degradation is 2:1 in count and nearly 2:1 in total magnitude vs. improvements.

#### What happens mechanically (Q001 example):

- **Dense-only** retrieves gold chunk `dole_handbook_2023_min_wage_intro_coverage_rates` at **rank 1** (MRR=1.0).
- **Full pipeline** retrieves the same gold chunk at **rank 4** (MRR=0.25) because RRF interleaves `RA-10361-06`, `book3-title2-articles123-127-wage-standards`, and `book3-title2-articles97-101-wages-definitions` above it. These are topically adjacent articles that lexical search ranks highly (keyword overlap with "minimum wage") but are not the gold chunk.

**This pattern repeats in 24 of 26 degraded queries:** dense puts gold at rank 1, then lexical/symbolic contribute topically-related-but-incorrect chunks that accumulate enough RRF score to displace the gold chunk.

### 2.2 Degradation by Retrieval Target

| Target | Degraded / Total | Degradation Rate | Avg MRR Loss |
|--------|-----------------|-----------------|-------------|
| dense | 9/25 | 36% | 0.496 |
| hybrid | 9/25 | 36% | 0.519 |
| lexical | 4/25 | 16% | 0.596 |
| symbolic | 4/25 | 16% | 0.471 |

**Dense-target and hybrid-target queries** are most affected (36% degradation rate each). These are the queries where dense retrieval alone achieves near-perfect ranking and the other strategies introduce noise.

### 2.3 Dense Dominates All Four Target Groups

Average MRR@5 by retrieval_target:

| Target (n=25 each) | Dense-only | Lexical-only | Symbolic-only | Hybrid |
|---------------------|-----------|-------------|--------------|--------|
| dense | **0.777** | 0.581 | 0.600 | 0.685 |
| lexical | **0.900** | 0.803 | 0.493 | 0.845 |
| symbolic | 0.813 | 0.827 | **0.953** | 0.895 |
| hybrid | **0.900** | 0.767 | 0.337 | 0.723 |

Dense-only is the **best or tied-best MRR strategy in 3 of 4 target groups** (dense, lexical, hybrid). Only in the symbolic group does symbolic surpass dense. The hybrid pipeline fails to beat dense in any group except symbolic.

**Critical insight:** Even for lexical-target queries, dense MRR (0.900) > lexical MRR (0.803). The query set does not sufficiently differentiate what each strategy is uniquely good at.

### 2.4 The "Universal Competence" Problem

Dense retrieval in this system benefits from two advantages that make it unnaturally strong:

1. **Stage 1 normalized query**: All variants (including dense-only) pass through query analysis, which translates non-EN queries to English and rephrases them. This gives dense embeddings a polished, English-normalized query to embed — exactly what `text-embedding-3-small` was trained on.

2. **High-quality KB embeddings**: The knowledge base is well-structured with clean, topically coherent chunks. Dense cosine similarity against well-organized legal text is naturally effective — the embedding space clusters related provisions together.

As a result, dense retrieval achieves 98% HR@5 and 0.848 MRR@5 *on its own*. There is very little room for other strategies to add value (only 2 HR@5 misses out of 100 queries).

### 2.5 Why RRF Math Favors Rank Dilution

With weights `dense=1.0, lexical=0.75, symbolic=0.10` and `k=60`:

- A gold chunk at dense rank 1: `1.0/(60+1) = 0.01639`
- A non-gold chunk at dense rank 3, lexical rank 1: `1.0/(60+3) + 0.75/(60+1) = 0.01587 + 0.01230 = 0.02817`

The non-gold chunk **outscores** the gold chunk because it accumulates contributions from multiple strategies. This is the fundamental RRF tradeoff — fusion rewards consensus across strategies, not confidence within a single strategy. When dense is already optimal, consensus = noise injection.

---

## 3. Where Hybrid Actually Helps

### 3.1 The 13 Improved Queries

| Query | Target | Lang | Dense MRR | Pipe MRR | What Saved It |
|-------|--------|------|----------|---------|--------------|
| Q010 | symbolic | fil | 0.500 | 1.000 | sym+lex agreement |
| Q011 | lexical | ceb | 0.500 | 1.000 | sym agreement |
| Q014 | dense | ceb | 0.500 | 1.000 | sym+lex agreement |
| Q019 | symbolic | en | 0.250 | 1.000 | lex+sym boosted gold |
| Q039 | dense | ceb | 0.500 | 1.000 | lex+sym agreement |
| Q062 | hybrid | ceb | 0.250 | 0.500 | lex boosted gold |
| Q066 | dense | en | 0.333 | 1.000 | lex boosted gold |
| Q083 | symbolic | fil | 0.333 | 1.000 | lex+sym agreement |
| Q088 | symbolic | fil | 0.333 | 1.000 | sym boosted gold |
| Q089 | symbolic | en | 0.333 | 1.000 | sym boosted gold |
| Q095 | symbolic | ceb | 0.333 | 1.000 | lex+sym agreement |
| Q096 | lexical | en | 0.500 | 1.000 | lex agreement |
| Q098 | dense | en | 0.500 | 1.000 | sym agreement |

**Pattern:** Hybrid rescues occur primarily when dense ranks gold at position 2-4, and another strategy independently ranks it at position 1. The RRF multi-source agreement then pushes it to the top.

**8 of 13 improvements** (62%) involve symbolic retrieval agreeing with the gold chunk — this is the direct payoff from the keyword column enrichment.

### 3.2 Zero Pipeline Rescues at HR@5 Level

There are **zero queries** where dense HR@5=0 but pipeline HR@5>0. Dense already hits 98% HR@5 — the 2 misses (Q035, Q087) are also missed by the pipeline. The hybrid pipeline cannot rescue queries that all strategies fail on.

---

## 4. Why the Query Set Favors Dense

### 4.1 Insufficient Lexical-Specific Differentiation

For lexical-target queries, dense still achieves MRR 0.900 vs. lexical's 0.803. This means the lexical-target queries are not actually "hard for dense" — they are queries that happen to contain lexical patterns, but whose gold chunks are also semantically similar to the query embedding.

**To make lexical-target queries genuinely challenge dense**, they would need to:
- Use highly specific legal terminology that embeds poorly (acronyms, procedural jargon)
- Target chunks with high keyword overlap but low semantic similarity to the query embedding
- Use exact-match requirements (e.g., searching for a specific form number or procedural rule identifier)

### 4.2 Dense-Target Queries Are Not Hard Enough

Dense-target queries achieve 0.777 MRR in dense-only, but **the same queries achieve 0.600 MRR in symbolic-only**. This means 60% of "dense-target" queries are also partially solvable by symbolic lookup (likely because the gold chunks contain explicit article references that the keyword column captures).

### 4.3 Hybrid-Target Queries Under-Utilize Multi-Strategy Agreement

Hybrid-target queries (designed to need all strategies) show dense MRR=0.900 vs. pipeline MRR=0.723. This is the **worst hybrid degradation** of any target group. The queries labeled "hybrid" are not actually requiring multi-strategy agreement — dense alone handles them well.

---

## 5. Potential Solutions

### 5.1 Solution A: Redesign Query Set to Create Genuine Strategy Niches (Recommended)

**Goal:** Ensure each retrieval_target group contains queries where the "correct" strategy **clearly excels** and dense **genuinely struggles**.

**Validation criterion per query:** `lexical_only MRR@5 ≥ 0.5` AND `dense_only MRR@5 ≤ 0.5`

---

#### 5.1.1 Current Lexical State (25 queries)

| Category | n | Avg Words | Dense MRR@5 | Lexical MRR@5 |
|----------|---|-----------|-------------|---------------|
| Lexical Wins (dense < lexical) | 5 | 64 | 0.500 | 1.000 |
| Ties (both = 1.0) | 19 | 77 | 1.000 | 1.000 |
| Dense Wins (dense > lexical) | 1 | 105 | 1.000 | 0.250 |

Dense achieves MRR@5=1.0 on **20 of 25** lexical-target queries. The queries are too long and too semantically precise, giving `text-embedding-3-small` enough signal to find the gold chunk at rank 1 despite the presence of FTS-exploitable terms.

#### 5.1.2 Root Cause: Dense Spoiler Mechanism

In the 5 queries where lexical wins, dense puts a **spoiler chunk** (same document family / topic area) at rank 1 instead of gold:

| QID | Gold Chunk | Dense Rank-1 Spoiler | Shared Family |
|-----|------------|---------------------|---------------|
| Q001 | `min_wage_intro_coverage_rates` | `min_wage_kasambahay_tax_bmbe` | DOLE min-wage |
| Q025 | `service_charges_sil` | `articles91-96-weekly-rest-holidays` | compensation |
| Q057 | `RA-10361-06` | `articles102-105-payment-mechanics` | payment rules |
| Q092 | `sena_preamble_rule1_definitions` | `sena_rule3_seado_duties_conduct` | SEnA |
| Q096 | `covid_duties_responsibilities` | `covid_testing_compliance` | COVID protocols |

In all 5 cases, the spoiler's embedding is nearest to the query because both gold and spoiler cover the same topic area. FTS discriminates using verbatim terms that appear only in the gold chunk.

In the 19 tied queries, dense succeeds because the query's semantic content maps **uniquely** to the gold chunk — no spoiler in the same topic area is closer.

#### 5.1.3 Lexical Query Properties (Redesign Guide)

**P1. Semantic Neighbor Confusion (Core Mechanism)**
The gold chunk must have a semantically similar spoiler in the KB — a chunk in the same document family or topic cluster. Dense cannot reliably distinguish gold from spoiler; FTS can via distinctive term matching.

> **Prerequisite**: Before writing a query, identify ≥1 spoiler chunk that shares the gold's topic. If the gold chunk is topically unique in the KB, dense will always find it at rank 1 — it is a poor candidate for lexical-target.

**P2. Lexical Discriminator — FTS-Matchable, Embedding-Opaque Terms**
Include 1–3 distinctive terms that:
  - (a) Appear verbatim in the gold chunk's `full_text`
  - (b) Do NOT appear in the spoiler chunk(s)
  - (c) Are poor semantic embedders — they don't shift the embedding toward gold vs. spoiler

Good discriminator categories:
| Category | Examples |
|----------|---------|
| Acronyms | BMBE, SEADO, SEAD, IEC, SIL, EEMR, PPD, PTD, AEP |
| Named programs/forms | KaGabay, Batas Kasambahay, SEnA referral |
| Enumerated items | "promissory notes, vouchers, coupons, tokens" |
| Verbatim policy phrases | "distributed completely and equally", "shuttle services" |
| Specific amounts/formulas | ₱1,000, "Factor 305", "4.5% premium rate" |

Counter-example: In tied Q009, the phrase "Factor 305 may be used instead of 313" looks lexical but is also embedding-distinctive because the numerical combination (395, 293.0, 67.6, 313, 305) creates a unique semantic fingerprint. **Numbers + surrounding context can be discriminative for BOTH FTS and dense** — use them cautiously.

**P3. Length — Short-to-Moderate (35–65 words)**
Long queries (>70 words) provide too much context for `text-embedding-3-small`. The `normalized_query_en` creates a precise embedding that uniquely maps to the gold chunk even when spoilers exist.

Winners average 64 words; ties average 77 words; the lone failing query (Q030) is 105 words.

**P4. Ask, Don't Describe**
Queries that paraphrase the gold chunk in detail create a unique semantic fingerprint that dense embeds precisely.

- ❌ Anti-pattern (Q009, TIE): *"ang EEMR formula... factor 395... 293.0 ordinary working days... 67.6 rest days... Factor 305..."* — exhaustively describes the gold chunk content → dense maps it uniquely.
- ✅ Good pattern (Q092, WIN): *"What does 'SEADO' stand for, and what is 'SEAD'?"* — asks a focused question using discriminator terms without summarizing the gold.

**P5. No Law Citations in `query_text`** (hard rule)
- ❌ Never include `Article N`, `RA NNNN`, `PD NNN`, `DO NNN-NN`, `LOI NNN` — triggers `_extract_articles_regex` → populates `articles[]` → symbolic search contaminates lexical signal.
- ❌ Never reference a law by name if the LLM can infer the citation (e.g., "PD 851 Implementing Rules" → LLM extracts `PD 851`). Use topic descriptions without decree numbers.
- ✅ Keep `gold_article_refs` accurate for human review — citations belong there, not in `query_text`.

**P6. FTS Dual-Signal Awareness**
`keyword_search` uses TWO FTS signals via `GREATEST()`:
1. **Keyword-OR**: LLM-extracted keywords joined with "OR" → `websearch_to_tsquery('english', 'term1 OR term2 OR term3')`
2. **Raw-query**: Full `normalized_query_en` → `websearch_to_tsquery('english', full_text)`

`websearch_to_tsquery` joins adjacent words with AND. For long queries (>70w), the AND conjunction of 50+ stems is too restrictive → matches nothing → only keyword-OR signal survives (often too generic). For moderate queries (35–65w), both signals contribute meaningful discrimination.

#### 5.1.4 Per-Query Validation Checklist

1. ☐ Gold chunk has ≥1 spoiler chunk in the same topic/document family
2. ☐ Query contains 1–3 FTS discriminators (acronyms, enumerated items, policy phrases) present in gold but NOT in spoiler
3. ☐ Query ≤ 65 words (preferred; ≤ 80 if discriminator quality is high)
4. ☐ Query asks about gold content without paraphrasing it extensively
5. ☐ No law citations in `query_text` (no `Article N`, `RA N`, `PD N`, `DO N-N`)
6. ☐ Expected result: `dense_only MRR@5 ≤ 0.5`, `lexical_only MRR@5 ≥ 0.5`

---

**For symbolic-target queries (n=25), keep current design** (already well-differentiated after keyword enrichment: sym=0.953 vs dense=0.813). No redesign needed.

---

#### 5.1.5 Dense-Target Query Properties (Redesign Guide)

**Goal:** `dense_only MRR@5 ≥ 0.8` AND `lexical_only MRR@5 ≤ 0.4` AND `symbolic_only MRR@5 ≤ 0.4`

Dense-target properties are the near-inverse of lexical-target. The goal is to give dense an unambiguous embedding signal while eliminating every foothold for FTS and symbolic.

**DP1. Topically Unique Gold (¬P1)**
Gold chunk has **no close semantic neighbor** in the KB. Dense maps the query precisely to gold without spoiler confusion. Choose chunks that stand alone in their topic area (unique procedural guides, specialized benefit computations with no sibling sections).

> **Prerequisite**: Verify that no other KB chunk covers the same concept before writing the query. If siblings exist, the gold is a better candidate for lexical-target.

**DP2. Semantic Paraphrase — No Verbatim Terms (¬P2)**
Describe the legal concept in conceptual or colloquial language — workplace-scenario framing, plain-language interpretations, synonyms. Do NOT quote verbatim policy phrases, acronyms, or procedural names from the gold chunk. `websearch_to_tsquery` cannot match paraphrased stems → FTS retrieves nothing useful.

**DP3. Long Query — 60–100 Words (¬P3)**
Rich descriptive content gives `text-embedding-3-small` a highly specific embedding vector. As a side effect, `websearch_to_tsquery` AND-joins all 50+ normalized stems → excessively restrictive → raw-query FTS signal completely breaks. LLM-extracted keywords also become generic because the paraphrase (DP2) yields no distinctive stems.

**DP4. Describe, Don't Ask (¬P4)**
Narrate the scenario, legal implication, or policy context. Dense handles concept→content mapping natively; a short focused question produces a generic embedding. A rich situational description creates a unique semantic fingerprint that maps precisely to gold.

- ❌ Anti-pattern: *"What does BMBE exemption mean?"* — short, too explicit
- ✅ Good pattern: *"A small enterprise registered with the MSMED Council claims exemption from wage orders because of its micro-scale barangay-level classification. Describe the procedure the employer must follow to validate and sustain this exemption."*

**DP5. No Law Citations (P5 — same as lexical)**
No `Article N`, `RA N`, `PD N`, `DO N-N` in `query_text`. Prevents symbolic from triggering. Gold chunks should ideally be DOLE handbook sections or policy interpretations — not chunks directly mapped from a single statutory article.

**DP6. FTS Intentionally Broken (¬P6)**
The long query (DP3) and paraphrase (DP2) together break both FTS signals: the raw-query AND signal fails due to length; the keyword-OR signal produces only generic stems (e.g., "employee," "employer") that match dozens of chunks equally. Both failures are by design.

#### 5.1.6 Dense-Target Validation Checklist

1. ☐ No KB chunk semantically similar to gold (no spoiler candidate exists)
2. ☐ Query uses only paraphrased, non-verbatim language — no terms directly quoted from gold
3. ☐ Query ≥ 60 words
4. ☐ Query describes a scenario or concept, not a question about a specific term
5. ☐ No law citations in `query_text`
6. ☐ Expected result: `dense_only MRR@5 ≥ 0.8`, `lexical_only MRR@5 ≤ 0.4`, `symbolic_only MRR@5 ≤ 0.4`

---

#### 5.1.7 Hybrid-Target Query Properties (Redesign Guide)

**Goal:** All three strategies individually fail (`MRR@5 ≤ 0.5`), combined via RRF: `hybrid MRR@5 ≥ 0.8`

The hybrid query must give each strategy **partial but insufficient signal** toward gold, while ensuring that each strategy has a *different* spoiler at rank 1. RRF then elevates gold through cross-strategy agreement.

**RRF mechanics enabler:** If gold ranks 2nd in dense, 2nd in lexical, and 2nd in symbolic — while three different spoilers each lead a different strategy — gold's accumulated multi-strategy RRF score outranks any single-strategy spoiler:

| Result | Dense | Lexical | Symbolic | RRF Score |
|--------|-------|---------|----------|-----------|
| Gold | rank 2 | rank 2 | rank 2 | 3× second-rank contributions |
| Spoiler A | **rank 1** | rank 5 | rank 5 | 1× first-rank, 2× deep-rank |
| Spoiler B | rank 5 | **rank 1** | rank 5 | 1× first-rank, 2× deep-rank |
| Spoiler C | rank 5 | rank 5 | **rank 1** | 1× first-rank, 2× deep-rank |

Gold wins fusion even though it never leads any individual strategy.

**HP1. Multiple Semantic Spoilers (Enhanced P1)**
Gold has ≥2 semantically similar chunks in the same document family. Dense is confused by multiple neighbors; Spoiler A beats gold in embedding space. Gold lands at dense rank 2–3, not rank 1.

**HP2. Shared (Weak) FTS Anchor — Present in Gold AND One Spoiler (Partial P2)**
Include 1 FTS-matchable term that appears in BOTH gold AND one spoiler. This gives lexical enough signal to include gold in its candidate set (rank 2–3), but the shared term prevents lexical from ranking gold above that spoiler.

| P2 Variant | Behavior | Outcome |
|------------|----------|---------|
| Strong P2 (exclusive term) | Lexical ranks gold #1 | Lexical wins alone — **wrong for hybrid** |
| Partial P2 (shared term) | Gold at lexical rank 2–3 | Lexical contributes to RRF but can't win alone ✅ |
| ¬P2 (no term) | Gold misses lexical entirely | No lexical RRF contribution for gold — **defeats hybrid** |

**HP3. Moderate Length — 40–70 Words (P3-like)**
Keeps both FTS signals partially active. Unlike ¬P3 for dense-target where FTS is intentionally broken, hybrid-target needs `keyword_search` to return meaningful candidates (gold in top-3, just not rank 1).

**HP4. Mixed Describe + Ask (Blend of P4 and DP4)**
Include both: a descriptive/scenario element (gives dense semantic signal → gold at dense rank 2–3) AND a question about a specific element (gives lexical a partial FTS hook). Pure DP4 (describe only) risks dense succeeding alone; pure P4 (ask only with strong discriminators) risks lexical succeeding alone.

**HP5. Broad/Implied Law Reference (¬P5)**
This is the **key divergence** from lexical-target and dense-target rules. Reference the law or document family by **concept or common name** (e.g., "the domestic worker law records requirement"), not a specific section. The LLM extracts a broad article reference → symbolic retrieves the document family → gold is one of several candidate sections → gold at symbolic rank 2–3.

- ❌ Anti-pattern (too specific): *"Under Section 2 of PD 851..."* → symbolic finds exactly gold → symbolic wins alone
- ❌ Anti-pattern (no reference, P5): symbolic never triggers → hybrid becomes dense+lexical only, not tri-strategy fusion
- ✅ Good pattern: *"Under the rules on domestic workers' employment records..."* → LLM may extract `RA-10361` broadly → symbolic gets the Kasambahay Law family → gold is one of several sibling sections

**HP6. Both FTS Signals Partially Active (P6-like)**
Moderate length (HP3) and a partial FTS anchor (HP2) keep `keyword_search` competitive. Unlike dense-target where FTS is intentionally broken, hybrid-target depends on lexical contributing a real (if partial) signal toward gold.

#### 5.1.8 Hybrid-Target Validation Checklist

1. ☐ Gold has ≥2 sibling chunks in same document family (multiple confusable spoilers)
2. ☐ Query contains 1 FTS-matchable term present in BOTH gold and one spoiler (weak shared anchor)
3. ☐ Query is 40–70 words
4. ☐ Query blends scenario description (dense hook) with a minor question (lexical hook)
5. ☐ Query implies a law/document family by concept name, no specific section number (symbolic hook)
6. ☐ Expected result: all three single-strategy MRR@5 ≤ 0.5, hybrid MRR@5 ≥ 0.8

---

#### 5.1.9 Cross-Target Property Comparison

| Property | Lexical-Target | Dense-Target | Hybrid-Target |
|----------|:---:|:---:|:---:|
| Semantic neighbors (P1) | ✅ ≥1 spoiler required | ❌ Gold is unique | ✅ ≥2 spoilers required |
| FTS discriminators (P2) | ✅ Exclusive to gold | ❌ None — paraphrase only | ⚡ Shared with 1 spoiler |
| Query length (P3) | 35–65 words | 60–100 words | 40–70 words |
| Ask vs. Describe (P4) | Ask (focused question) | Describe (scenario) | Mix (context + question) |
| Law citations (P5) | ❌ Forbidden | ❌ Forbidden | ⚡ Broad/implied only |
| FTS dual-signal (P6) | ✅ Both signals active | ❌ Intentionally broken | ✅ Partially active |
| Symbolic signal | Off (P5) | Off (P5) | ⚡ Broad family (¬P5) |

⚡ = Modified/partial application

**Validation of user's hybrid hypothesis (P1, ¬P2, P4, P5, ¬P6):**
| Property | User Proposed | Correct | Issue if Wrong |
|----------|:---:|:---:|---|
| P1 (semantic neighbors) | ✅ | ✅ | — |
| ¬P2 (no FTS terms) | ❌ | Partial P2 | Gold misses lexical entirely → zero lexical RRF contribution |
| P4 (ask) | ❌ | Mixed P4/DP4 | Pure question + good discriminator risks lexical winning alone |
| P5 (no citations) | ❌ | ¬P5 (broad ref) | Symbolic never triggers → no tri-strategy fusion |
| ¬P6 (long query) | ❌ | P6-like (moderate) | Long query breaks FTS entirely, same problem as ¬P2 |

### 5.2 Solution B: Adaptive Strategy Gating (Code Change)

Instead of always running all 3 strategies, **selectively gate strategies** based on query analysis signals:

```
if query has explicit article references:
    enable symbolic (high weight)
if query has specific legal terms / exact phrases:
    enable lexical (high weight)
always enable dense (baseline)
```

This prevents lexical/symbolic from injecting noise on queries where they have no useful signal. The downside is added complexity and potential for gating errors.

### 5.3 Solution C: Increase RRF k Constant or Dense Weight

- Increasing `k` (currently 60) dilutes per-rank differences, making RRF rank more stable
- Increasing the dense weight relative to others (e.g., dense=1.0, lexical=0.5, symbolic=0.05) reduces noise from weaker strategies
- **Limitation:** This was already explored in HPT Rounds 1-3. Further weight adjustments yield diminishing returns because the fundamental issue is query design, not weight tuning.

### 5.4 Solution D: Weighted Score Fusion Instead of RRF

Replace rank-based RRF with **score-based weighted fusion**:

```
final_score(d) = w_dense * cosine_sim(d) + w_lex * normalized_fts_rank(d) + w_sym * overlap_score(d)
```

This preserves the magnitude of dense confidence signals rather than discarding them into rank positions. A chunk at dense cosine 0.95 would dominate over a chunk at cosine 0.65 that happens to also be lexical rank 1.

**Tradeoff:** Requires score normalization across strategies with different score ranges (cosine 0.3-1.0 vs FTS 0.01-0.1).

---

## 6. Recommended Action Plan

### Priority 1 — Redesign Query Set (No code change)

This is the most defensible approach for a thesis evaluation. The current query set does not provide sufficient differentiation between strategy niches — dense can solve most queries regardless of their labeled target.

**Steps:**
1. For lexical-target queries: introduce queries requiring exact-match terminology, procedural jargon, or form-number lookups where embeddings would fail.
2. For hybrid-target queries: ensure they require partial signals from multiple strategies (e.g., a paraphrased concept + an explicit article reference).
3. Validate changes: each redesigned query should pass the criterion "the designated strategy achieves MRR@5 >= 0.8 while dense-only achieves MRR@5 <= 0.5."
4. Re-run Phase 1 after query redesign.

### Priority 2 — Evaluate Score-Based Fusion (Code change, optional)

If query redesign alone does not suffice, implement a score-based fusion alternative and compare against RRF. This would be an additional experimental finding for the thesis.

---

## 7. Key Takeaway

The hybrid pipeline's MRR deficit is **not a system bug** — it is a consequence of:
1. Dense retrieval being exceptionally effective on this query set (98% HR, 84.8% MRR)
2. RRF by design redistributing rank mass across strategies, penalizing high single-strategy confidence
3. The query set insufficiently differentiating between strategy niches

The fix is not to make the retrieval code different, but to **ensure the evaluation queries create genuine scenarios where multi-strategy fusion is necessary** — which currently only 13 of 100 queries demonstrate.
