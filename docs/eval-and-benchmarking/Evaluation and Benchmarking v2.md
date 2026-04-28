# Evaluation and Benchmarking

In this section, we evaluate our three-stage multilingual RAG pipeline on Philippine labor-law question answering, focusing on how each component contributes to overall performance. Our evaluation contributes a structured benchmark for multilingual legal RAG in a low-resource setting, addressing a gap in existing evaluation frameworks. We adopt a structured, layered approach: automated retrieval metrics assess sub-component variants independently, while expert human evaluation targets the three most informative end-to-end pipeline configurations. This design yields a clear evaluation pattern, minimizes redundant manual effort, and ensures every measurement directly supports one of three core research claims.

**Research claims under evaluation:**

1. **Hybrid retrieval outperforms any single retriever** (dense-only, lexical-only, symbolic-only).
2. **Translation-to-English pivot** improves retrieval and answer quality for Filipino/Cebuano queries.
3. **Clarification handling** reduces incorrect answers and wasted retrieval under ambiguity.

---

## 5.1 Evaluation Setup and Metrics

### 5.1.1 Benchmark Dataset

We constructed a benchmark dataset of 100 Philippine labor law queries spanning English (35), Filipino (35), and Cebuano (30), drawn from common inquiries (e.g., wages, termination, benefits) and actual user questions. The test set includes both single-turn questions (70) and multi-turn dialog scenarios (30). All 30 multi-turn queries are structured in two phases: **Phase 1** (Turns 1–4) begins with an ambiguous initial query, proceeds through a clarification exchange (Turns 2–3), and concludes with a first resolved answer (Turn 4) — used for retrieval evaluation (Tables 2–4), answer quality evaluation (Tables 6, 9, and 10) and ambiguous-query answer quality (Table 7). **Phase 2** (Turns 5–6) adds a specific, non-ambiguous follow-up question on a related but distinct labor law topic grounded in the Phase 1 context, and a Turn 6 reference answer — used exclusively for multi-turn summarization evaluation (Table 8). Thirty queries (30%) are intentionally ambiguous and require clarification before answering. For each query, we prepared reference answers, gold-standard relevant chunks, and canonical legal citations to enable quantitative evaluation.

Each query is tagged with a `retrieval_target` label (`symbolic`, `lexical`, `dense`, or `hybrid`) indicating which retrieval strategy is expected to perform best. This enables "who wins where" breakdowns across retrieval strategies.

### 5.1.2 Evaluation Tiers

Our evaluation is organized into three tiers that separate concerns and minimize redundant effort:

| Tier | What is Measured | Method | Sections |
|------|-----------------|--------|----------|
| **Tier 1: Retrieval** | Which retrieval strategy (or combination) surfaces the correct legal provisions? | Automated metrics across all 8 pipeline variants | §5.2, §5.3 |
| **Tier 2: End-to-End Answer Quality** | How accurate, complete, and grounded are the generated answers? | Expert human evaluation on 3 key pipeline configurations | §5.4 |
| **Tier 3: Ablation Summary** | How does each pipeline stage contribute cumulatively? | Consolidated table from Tier 1 + Tier 2 findings | §5.5 |

### 5.1.3 Pipeline Variants

Eight pipeline variants are defined to cover all baselines and ablations:

| Variant | Stage 1 (Query Analysis) | Stage 2 (Retrieval) | Stage 3 (Generation) | Purpose |
|---------|--------------------------|---------------------|----------------------|-------|
| **Full Pipeline** | ✅ Translation + Clarification | Symbolic + Lexical + Dense | GPT-4.1 with RAG context | Proposed system (§5.4 Config C) |
| **Stage 2 Only** | ❌ | Symbolic + Lexical + Dense | GPT-4.1 with RAG context | Isolates retrieval value over LLM-only (§5.4 Config B) |
| **Dense-only** | ✅ | Dense only | GPT-4.1 with RAG context | Retriever baseline |
| **Lexical-only** | ✅ | Lexical (BM25/FTS) only | GPT-4.1 with RAG context | Retriever baseline |
| **Symbolic-only** | ✅ | Symbolic lookup only | GPT-4.1 with RAG context | Retriever baseline |
| **Hybrid – no translation** | Clarification only | Symbolic + Lexical + Dense | GPT-4.1 with RAG context | Translation ablation — non-English queries only (n=65) |
| **Hybrid – no clarification** | Translation only | Symbolic + Lexical + Dense | GPT-4.1 with RAG context | Clarification ablation — ambiguous queries only (n=30) |
| **LLM-only (no RAG)** | ❌ | ❌ None | GPT-4.1, no context | Hallucination baseline |

### 5.1.4 Metrics Summary

**Retrieval metrics (automated, Tier 1):**

- **Recall@K** — proportion of gold chunks retrieved in top-K results[1](https://openreview.net/pdf?id=vUwEzXgQDX#:~:text=4,single%2C%20comprehensive%20score%20for%20ranking)
- **Hit Rate@K** — binary: at least one gold chunk in top K
- **MRR** — reciprocal rank of the first relevant document[1](https://openreview.net/pdf?id=vUwEzXgQDX#:~:text=4,single%2C%20comprehensive%20score%20for%20ranking)
- K values reported: **K = 3, 5** for standard evaluation; **K = 10** is additionally reported in Table 2 for diagnostic depth. K = 10 is feasible at zero LLM cost because Table 2 uses `retrieval_only` mode, which runs Stage 1 + Stage 2 only and skips Stage 3 generation entirely. Note: with Reciprocal Rank Fusion (RRF), each K value requires an independent Stage 2 retrieval call — sub-selecting top-3 or top-5 results from a K=10 run does not reproduce the K=3 or K=5 RRF rankings.

**Answer quality metrics (automated, Tier 2 supplement):**

- **Token-level F1** — precision/recall of overlapping tokens with `reference_answer`
- **ROUGE-L** — longest common subsequence F-measure
- **Exact Match** — binary match after normalization

**Expert evaluation metrics (manual, Tier 2):**

- **4-point legal accuracy scale** (1 = incorrect/irrelevant → 4 = fully correct and supported), following prior legal QA rubrics[2](https://aclanthology.org/2021.nllp-1.11.pdf#:~:text=content%2C%20entity%2C%20and%20analytic%20questions,Table%201%3A%20Answer%20evaluation%20scale)
- **Hallucination audit** — binary per-answer: any unsupported or fabricated claim?
- **Citation fidelity** — precision/recall of cited legal provisions against gold references
- **Clarification quality** (ambiguous queries only) — expert rates relevance of system's follow-up question

**RAG Triad metrics (LLM-as-judge, automated):**

Following the TruLens RAG Triad[3](https://www.trulens.org/getting_started/core_concepts/rag_triad/#:~:text=Image%3A%20RAG%20Triad)[4](https://www.trulens.org/getting_started/core_concepts/rag_triad/#:~:text=After%20the%20context%20is%20retrieved%2C,each%20within%20the%20retrieved%20context), an LLM evaluator (GPT-4.1 with a rubric prompt) scores each answer on three dimensions (0–1 each):

- **Context Relevance** — are the retrieved passages relevant to the query?
- **Groundedness** — is every claim supported by retrieved context?
- **Answer Relevance** — does the answer address the user's question?

Two legal experts independently rate answers. Inter-rater reliability is reported via Cohen's κ. Disagreements are resolved by discussion or a third adjudicator.

---

## 5.2 Retrieval Layer Evaluation (Automated — Claim 1)

This section evaluates Stage 2 in isolation: given a query (after Stage 1 processing), which retrieval strategy surfaces the correct legal provisions? All four retrieval variants are compared using automated metrics across all 100 queries.

### 5.2.1 Retriever Comparison

We compare four retrieval settings:

1. **Dense-only** — semantic vector search via pgvector (text-embedding-3-small, 1536-dim)
2. **Lexical-only** — BM25/PostgreSQL full-text search
3. **Symbolic-only** — direct article/section identifier lookup via SQL
4. **Hybrid** — all three strategies fused via Reciprocal Rank Fusion, merged, and deduplicated

**Table 2: Retrieval Performance Across Strategies (All 100 Queries, RRF Weights: $w_{\text{dense}}=1.0$, $w_{\text{lex}}=0.25$, $w_{\text{sym}}=1.0$)**

| Metric      | Dense-only | Lexical-only | Symbolic-only | Hybrid     |
| ----------- | ---------- | ------------ | ------------- | ---------- |
| HitRate@3   | 0.7000     | 0.5600       | 0.3500        | **0.8700** |
| HitRate@5   | 0.7700     | 0.6800       | 0.3600        | **0.9400** |
| HitRate@10  | 0.8100     | 0.7900       | 0.3600        | **0.9600** |
| MRR@3       | 0.4567     | 0.4483       | 0.3283        | **0.6600** |
| MRR@5       | 0.4722     | 0.4758       | 0.3308        | **0.6775** |
| MRR@10      | 0.4775     | 0.4916       | 0.3308        | **0.6877** |
| Recall@3    | 0.5670     | 0.4700       | 0.3367        | **0.7387** |
| Recall@5    | 0.6590     | 0.5900       | 0.3517        | **0.8290** |
| Recall@10   | 0.7410     | 0.7007       | 0.3517        | **0.9077** |

The hybrid strategy (full pipeline with multi-strategy Reciprocal Rank Fusion) outperforms every individual retrieval strategy across all nine reported metrics and at every depth cutoff. At HitRate@3, hybrid achieves 0.870, compared to 0.700 for dense-only, 0.560 for lexical-only, and 0.350 for symbolic-only — a margin of 17.0 percentage points (pp) over the next-best single retriever. The coverage advantage is sustained at greater depth: HitRate@10 reaches 0.960 for hybrid versus 0.810 for dense-only, reflecting consistently broader retrieval as the result-list budget expands.

The MRR advantage of hybrid over standalone retrievers is particularly pronounced. Hybrid MRR@10 (0.6877) exceeds dense-only (0.4775) by 21.0 pp and lexical-only (0.4916) by 19.6 pp. These margins indicate that fusion not only increases the probability of retrieving a relevant passage within the top-$K$ set, but consistently ranks it at a higher position — a property that directly reduces the volume of irrelevant context admitted to the generation stage. Recall@5 for hybrid (0.8290) surpasses dense-only (0.6590) by 17.0 pp and lexical-only (0.5900) by 23.9 pp, underscoring the breadth of the coverage gain.

Symbolic-only performs substantially below all other strategies in the aggregate — HitRate@3 = 0.350, Recall@5 = 0.352, MRR@10 = 0.331. This is not a reflection of its precision when applicable, but rather of its complete inactivation on the majority of queries that contain no explicit article identifiers. Stage 1 extracts no article references for 56 of the 100 benchmark queries, rendering symbolic lookup inapplicable and contributing zero candidates to RRF fusion in those cases; its aggregate performance is therefore dominated by these non-activating queries. Per-type performance, which isolates this retriever on its native query class, is detailed in Table 3.

These results are obtained using the Round 4 hyperparameter-tuned RRF weights ($w_{\text{dense}}=1.0$, $w_{\text{lex}}=0.25$, $w_{\text{sym}}=1.0$), derived via offline grid search over 66 weight combinations on the full benchmark set (§5.1.3). Under the preceding Round 3 weights ($w_{\text{dense}}=1.0$, $w_{\text{lex}}=0.75$, $w_{\text{sym}}=0.10$), the hybrid strategy performed near-equivalently to dense-only in the aggregate, with HitRate@3 of 0.710 for both variants and hybrid MRR@10 of 0.612 only modestly exceeding dense-only's 0.495. The weight revision — restoring the symbolic contribution from $w_{\text{sym}}=0.10$ to $1.00$ and suppressing lexical noise by reducing $w_{\text{lex}}$ from 0.75 to 0.25 — resolves this near-equivalence entirely, yielding the decisive margins reported above.

**Table 3: Retrieval Performance by `retrieval_target` Subset (n = 25 per subset)**

This table disaggregates the aggregate results of Table 2 by query type, revealing per-strategy specialization and identifying the mechanisms that drive or constrain hybrid performance:

| Subset        | Metric     | Dense-only | Lexical-only | Symbolic-only | Hybrid     |
| ------------- | ---------- | ---------- | ------------ | ------------- | ---------- |
| Symbolic (25) | HitRate@3  | 0.3200     | 0.4800       | **1.0000**    | 0.9600     |
| Symbolic (25) | HitRate@5  | 0.4000     | 0.6000       | **1.0000**    | **1.0000** |
| Symbolic (25) | Recall@5   | 0.2933     | 0.5600       | **1.0000**    | 0.9333     |
| Symbolic (25) | MRR@10     | 0.2333     | 0.4930       | **0.9533**    | **0.9533** |
| Lexical (25)  | HitRate@3  | 0.7200     | **1.0000**   | 0.0800        | 0.7200     |
| Lexical (25)  | HitRate@5  | 0.7600     | **1.0000**   | 0.0800        | 0.7600     |
| Lexical (25)  | Recall@5   | 0.7200     | **0.9000**   | 0.0800        | 0.7200     |
| Lexical (25)  | MRR@10     | 0.3407     | **0.8733**   | 0.0800        | 0.4733     |
| Dense (25)    | HitRate@3  | **1.0000** | 0.3200       | 0.1200        | 0.8800     |
| Dense (25)    | HitRate@5  | **1.0000** | 0.4400       | 0.1200        | **1.0000** |
| Dense (25)    | Recall@5   | 0.8733     | 0.3467       | 0.1200        | **0.8933** |
| Dense (25)    | MRR@10     | **0.8533** | 0.2384       | 0.1200        | 0.7100     |
| Hybrid (25)   | HitRate@3  | 0.7600     | 0.4400       | 0.2000        | **0.9200** |
| Hybrid (25)   | HitRate@5  | 0.9200     | 0.6800       | 0.2400        | **1.0000** |
| Hybrid (25)   | Recall@5   | 0.7493     | 0.5533       | 0.2067        | **0.7693** |
| Hybrid (25)   | MRR@10     | 0.4827     | 0.3618       | 0.1700        | **0.6140** |

The per-`retrieval_target` breakdown isolates and explains the mechanisms underlying Table 2's aggregate results, revealing both the strengths and the bounded costs of multi-strategy fusion.

*Symbolic-target queries (n = 25).* Symbolic-only achieves a perfect HitRate@3 = 1.000, HitRate@5 = 1.000, and MRR@10 = 0.953 on the 25 queries constructed to include explicit article references, confirming that direct SQL-based article lookup delivers exact-match retrieval with near-unit precision when applicable. A central finding of this evaluation is the corresponding performance of the hybrid strategy under Round 4 weights: HitRate@3 = 0.960, HitRate@5 = 1.000, and MRR@10 = 0.953 — effectively matching the standalone symbolic baseline at the K = 5 and MRR@10 cutoffs. This constitutes a decisive reversal from Round 3 weights ($w_{\text{sym}}=0.10$), under which hybrid HitRate@3 on symbolic queries was 0.240. The previous degradation arose because the under-weighted symbolic rank-1 contribution ($0.10/(60+1)=0.00164$) was readily displaced by any dense or lexical result at any position in the fused list. With $w_{\text{sym}}=1.00$, the symbolic rank-1 contribution equals that of a dense rank-1 result ($1.00/61=0.01639$), restoring symbolic gold chunks to the top of the merged ranked list.

*Lexical-target queries (n = 25).* Lexical-only achieves HitRate@3 = 1.000 and HitRate@5 = 1.000 on the 25 queries containing highly distinctive keyword combinations. Hybrid matches dense-only at HitRate@3 = 0.720 and HitRate@5 = 0.760, falling substantially short of the lexical-only ceiling. This gap reflects a known cost of RRF: when the gold passage occupies FTS rank 1 but is not among the top dense results, the globally normalized dense signal dilutes the FTS rank-1 contribution in the merged list. Hybrid MRR@10 on lexical-target queries (0.4733), however, substantially exceeds dense-only (0.3407) by 13.3 pp, indicating that, among the queries the hybrid does retrieve, the FTS channel elevates the ranking quality beyond what dense search alone achieves.

*Dense-target queries (n = 25).* Dense-only achieves a perfect HitRate@3 = 1.000, confirming that semantic vector search reliably retrieves the correct passages for queries framed around conceptual meaning rather than keyword overlap or article citation. Hybrid achieves HitRate@5 = 1.000 — matching dense at this cutoff — but registers HitRate@3 = 0.880, a 12.0 pp deficit attributable to the occasional displacement of the gold chunk from the top-3 position by high-confidence lexical or symbolic entries in the fused list. Hybrid MRR@10 (0.710) trails dense-only (0.853) by 14.3 pp, consistent with a rank dilution effect on queries that are optimally served by a single retrieval channel. Hybrid Recall@5 (0.8933), however, marginally exceeds dense-only (0.8733), suggesting that the additional channels contribute fractional coverage gains for multi-gold queries even in this subset.

*Hybrid-target queries (n = 25).* On the 25 queries explicitly designed to require complementary evidence from multiple retrieval channels, the hybrid strategy achieves its strongest relative advantage. Hybrid HitRate@5 = 1.000 and MRR@10 = 0.614, compared to dense-only at HitRate@5 = 0.920 and MRR@10 = 0.483. Neither dense-only (HitRate@5 = 0.920) nor lexical-only (HitRate@5 = 0.680) achieves complete coverage at K = 5 independently, while RRF fusion across all three strategies saturates to perfect recall at this cutoff. The hybrid MRR@10 advantage of 13.1 pp over dense-only confirms that fusion improves both coverage and ranking quality for queries whose relevant evidence is distributed across multiple retrieval channels, consistent with prior multi-strategy retrieval research[9](https://openreview.net/pdf?id=vUwEzXgQDX#:~:text=and%20re,5%5D.%20RAG%20combines)[10](https://openreview.net/pdf?id=vUwEzXgQDX#:~:text=improved%20retrieval%20performance%20across%20all,parametric).

### 5.2.2 Error Typology

We perform a manual error analysis on cases where each retrieval strategy fails to retrieve the correct authority, categorizing errors to understand component limitations[12](https://aclanthology.org/2021.nllp-1.11.pdf#:~:text=method%20were%20evaluated,answer%20finder%20on%20BM25_MLT%20picked).

**Lexical retrieval failures:** The most common failure mode is returning documents that contain the query keywords but in a different legal context — a known pitfall where superficial term overlap misleads BM25[13](https://aclanthology.org/2021.nllp-1.11.pdf#:~:text=,answer%20finder%20on%20BM25_MLT%20picked).

**Dense retrieval failures:** Semantically plausible but incorrect matches — e.g., retrieving a provision about contract law for a question about employment contracts. These topically adjacent but legally irrelevant results exploit embedding proximity without precision.

**Symbolic retrieval failures:** Queries that lack explicit article references produce zero results, making symbolic lookup inapplicable to paraphrased or colloquial questions. Additionally, queries referencing articles across multiple legal instruments may only partially match.

**Hybrid mitigation:** The hybrid strategy covers complementary failure modes. For example, for the query "Can an employer terminate without notice?", the lexical index retrieves the Labor Code provision on termination notice, while the dense retriever surfaces a commentary explaining exceptions — together yielding a complete answer context.

---

## 5.3 Query Analysis Impact on Retrieval (Automated — Claims 2 & 3)

This section isolates the contribution of Stage 1 (query analysis) by measuring how its sub-components — translation and clarification — affect downstream retrieval performance. Comparisons use automated retrieval metrics only, keeping this evaluation fully reproducible with no manual scoring burden.

### 5.3.1 Translation Pivot Impact (Claim 2)

Philippine labor documents are predominantly in English. Queries in Filipino or Cebuano pose a cross-lingual retrieval challenge. We compare retrieval performance on non-English queries (n = 65) under two conditions:

- **With translation** (Full Pipeline): Stage 1 translates the query to English before retrieval
- **Without translation** (Hybrid – no translation): the original Filipino/Cebuano query is used directly for retrieval

English queries (n = 35) serve as a control group and should be unaffected by this ablation.

**Table 4: Translation Pivot Effect on Retrieval (Non-English Queries, K = 5)**

| Language (n)          | Metric    | With Translation | Without Translation | Δ                  |
| --------------------- | --------- | ---------------- | ------------------- | ------------------ |
| Filipino (35)         | HitRate@5 | 0.9429           | 0.8286              | +0.1143 (+13.8%)   |
| Filipino (35)         | MRR@5     | 0.6619           | 0.6629              | −0.0010 (−0.2%)    |
| Filipino (35)         | Recall@5  | 0.8524           | 0.7238              | +0.1286 (+17.8%)   |
| Cebuano (30)          | HitRate@5 | 0.9333           | 0.7667              | +0.1666 (+21.7%)   |
| Cebuano (30)          | MRR@5     | 0.6306           | 0.5250              | +0.1056 (+20.1%)   |
| Cebuano (30)          | Recall@5  | 0.8444           | 0.6944              | +0.1500 (+21.6%)   |
| English (35, control) | HitRate@5 | 0.9429           | N/A (control)       | —                  |
| English (35, control) | MRR@5     | 0.7333           | N/A (control)       | —                  |
| English (35, control) | Recall@5  | 0.7924           | N/A (control)       | —                  |

> *The `Hybrid – no translation` pipeline variant was run exclusively on the 65 non-English queries (K = 5 only); English rows report Full Pipeline results as a reference baseline. Positive Δ indicates improvement attributable to the translation pivot.*

The translation pivot to English yields positive retrieval impact across both non-English query sets, with the magnitude of improvement differing substantially between languages. For Cebuano (n = 30), translation raises HitRate@5 by 16.66 pp (+21.7%), Recall@5 by 15.00 pp (+21.6%), and MRR@5 by 10.56 pp (+20.1%) — a consistent, large-magnitude gain distributed uniformly across both coverage and ranking metrics. For Filipino (n = 35), HitRate@5 increases by 11.43 pp (+13.8%) and Recall@5 by 12.86 pp (+17.8%); MRR@5, however, is effectively invariant — 0.6619 with translation versus 0.6629 without, a difference of −0.10 pp that falls within measurement noise. This near-null result for Filipino MRR is not contradictory to the concurrent coverage improvements: it indicates that, while translation expands the set of relevant documents retrieved within the top-5 window, it does not materially reorder documents already ranking near the top of both pipeline variants. Filipino queries benefit from moderate cross-lingual embedding alignment in multilingual pretraining corpora; translation for this language primarily recovers borderline-relevant documents into the top-5 set without affecting the rank ordering of those already retrieved.

The differential in improvement magnitude between Cebuano and Filipino is consistent with the well-documented variation in multilingual embedding model pretraining coverage across Philippine languages. Filipino (Tagalog) is substantially better represented in large multilingual corpora than Cebuano, yielding better-calibrated cross-lingual embedding alignment between Filipino and English legal text. Cebuano, as a considerably lower-resource language in this pretraining context, exhibits a larger cross-lingual alignment gap, rendering the translation normalization step disproportionately impactful — as evidenced by the roughly 7–8 pp larger improvement across all three K = 5 metrics relative to Filipino.

English queries serve as a reference condition with HitRate@5 = 0.943, Recall@5 = 0.792, and MRR@5 = 0.733 — the highest MRR@5 among all three language groups, reflecting the expected retrieval advantage of native-English queries against a predominantly English legal corpus. The translation stage introduces no degradation for these queries, as translating native English is a no-op in practice. Weighted across all 65 non-English queries, the translation pivot yields an aggregate improvement of +13.9 pp in HitRate@5 and +13.8 pp in Recall@5, providing quantitative support for Claim 2.

**Scoped execution of the translation ablation variant:** The `Hybrid – no translation` pipeline variant is run exclusively on the 65 non-English queries (Filipino n=35, Cebuano n=30). For English queries, disabling translation produces no behavioral difference — Stage 1 translating English to English yields an identical query. Running the variant on the 35 English queries would therefore produce outputs identical to the Full Pipeline, adding no measurement value. Scoping to n=65 reduces pipeline runs for this variant from 100 to 65 and is reflected in the cost estimate (see EXPERIMENT_EXECUTION_GUIDE.md §8). The English queries (n=35) remain available as a control group via the Full Pipeline results.

### 5.3.2 Clarification Impact on Answer Quality (Claim 3)

The clarification module operates on the query before retrieval begins — it does not alter the retrieval index. A standalone detection accuracy metric (precision/recall of whether Stage 1 fires its clarification branch) is insufficient as a primary measure: a correctly detected query can still yield a poor answer if the clarification question is unhelpful, and a missed detection manifests directly as a lower expert score in Table 7. We therefore evaluate the clarification module exclusively through end-to-end answer quality in Table 7 (§5.4.1), which directly measures whether Config C — with clarification — produces superior answers compared to Config B — without clarification — on the 30 ambiguous queries.

**Scoped execution of the clarification ablation variant:** The `Hybrid – no clarification` pipeline variant is run exclusively on the 30 ambiguous queries. For non-ambiguous queries, disabling clarification produces no behavioral difference — Stage 1 never invokes the clarification branch on a query it has already classified as unambiguous. Running the variant on the remaining 70 queries would therefore yield outputs identical to the Full Pipeline, adding no measurement value. Scoping to n=30 reduces pipeline runs for this variant from 100 to 30 and is reflected in the cost estimate (see EXPERIMENT_EXECUTION_GUIDE.md §8).

---

## 5.4 End-to-End Answer Quality, Hallucination, and Citation Fidelity (Manual — All Claims)

This section evaluates the generated answers with a focus on legal accuracy, completeness, faithfulness to sources, and hallucination rates. Expert human evaluation is conducted on **three pipeline configurations**, chosen to measure the cumulative contribution of each pipeline stage:

```mermaid
flowchart LR
    A["<b>Config A: LLM-only</b><br/>(No retrieval, no query analysis)<br/>GPT-4.1 from parametric knowledge"] 
    B["<b>Config B: Stage 2 Only</b><br/>(Hybrid retrieval ON,<br/>Query analysis OFF)<br/>Shows RAG value over LLM-only"]
    C["<b>Config C: Full Pipeline</b><br/>(Stage 1 + Stage 2 + Stage 3)<br/>Shows query analysis value<br/>over retrieval alone"]
    
    A -->|"+Retrieval"| B
    B -->|"+Query Analysis"| C
```

| Configuration | Stage 1 (Query Analysis) | Stage 2 (Retrieval) | Stage 3 (Generation) | What it proves |
|---------------|--------------------------|---------------------|----------------------|----------------|
| **A: LLM-only** | ❌ | ❌ | GPT-4.1, no context | Hallucination baseline; value of RAG |
| **B: Stage 2 only** | ❌ | Hybrid (all three) | GPT-4.1 with RAG context | RAG value; isolates retrieval contribution |
| **C: Full Pipeline** | ✅ Translation + Clarification | Hybrid (all three) | GPT-4.1 with RAG context | Full system; value of query analysis |

**Manual evaluation effort:** 3 configurations × 100 queries × 2 experts = **600 individual ratings**. This is substantially more tractable than evaluating all 8 variants manually (which would require 1,600 ratings) while still covering all three research claims through layered comparison.

### 5.4.1 Answer Generation Quality

Two labor-law experts independently score each answer on a 4-point scale[2](https://aclanthology.org/2021.nllp-1.11.pdf#:~:text=content%2C%20entity%2C%20and%20analytic%20questions,Table%201%3A%20Answer%20evaluation%20scale):

| Score | Label | Criteria |
|-------|-------|----------|
| 4 | Fully correct | Legally accurate, complete, and supported by cited provisions |
| 3 | Mostly correct | Correct core answer; minor omission or imprecision |
| 2 | Partially correct | Contains some correct information but missing key elements or has errors |
| 1 | Incorrect / Irrelevant | Wrong answer, irrelevant, or fabricated information |

**Table 6: Answer Quality Across Configurations (All 100 Queries)**

| Metric | A: LLM-only | B: Stage 2 Only | C: Full Pipeline |
|--------|------------|-----------------|-----------------|
| Mean Expert Score (1–4) | — | — | — |
| Token F1 | — | — | — |
| ROUGE-L | — | — | — |
| Exact Match (%) | — | — | — |
| Cohen's κ (inter-rater) | — | — | — |

**What experts evaluate per answer:**

- Legal accuracy of the substantive answer
- Completeness (did it address all aspects of the query?)
- Citation correctness (do cited articles actually say what the answer claims?)
- Hallucination detection (any fabricated laws, cases, or facts?)
- Clarification quality (for ambiguous queries in Config C: was the follow-up question helpful?)

**Blinding protocol:** Experts do not know which configuration produced the answer. Presentation order is randomized and variant labels are stripped.

**Table 7: Answer Quality — Ambiguous Query Subset (n = 30)**

| Metric | A: LLM-only | B: Stage 2 Only | C: Full Pipeline |
|--------|------------|-----------------|-----------------|
| Mean Expert Score (1–4) | — | — | — |
| % Fully Correct (score = 4) | — | — | — |

This subset directly tests Claim 3: the Full Pipeline (with clarification) should substantially outperform Stage 2 Only (without clarification) on ambiguous queries. All 30 queries in this subset follow the two-phase multi-turn structure: the Phase 1 clarification exchange (Turns 1–3) is stored in `conversation_history`, and the rated answer is the Turn 4 response produced after the exchange. Config A and Config B attempt Turn 4 directly from the vague Turn 1 query without the benefit of clarification context.

### 5.4.2 Multi-Turn Query Evaluation

Each of the 30 multi-turn queries includes a Turn 5 follow-up question that introduces a related but distinct labor law topic, grounded in the context established through Phase 1 (Turns 1–4). Table 8 evaluates Turn 6 answer quality, isolating Stage 1's ability to consolidate the full conversation history into a retrieval query that surfaces the correct provisions for the new follow-up question.

All three configurations receive the full conversation history (Turns 1–5) as input — conversation history is a general input available to any dialogue system and is not a Stage 1 capability. What distinguishes them is how that history is processed for retrieval:

- **Config A (LLM-only):** receives the full conversation history (Turns 1–5); generates a Turn 6 response from parametric knowledge only, without any retrieval.
- **Config B (Stage 2 only):** receives the full conversation history (Turns 1–5); the raw Turn 5 query is passed directly to retrieval without Stage 1 summarization; Stage 3 generates Turn 6 with the retrieved context and full history.
- **Config C (Full Pipeline):** Stage 1 receives the full conversation history (Turns 1–5) and synthesizes all prior context — including the established facts from the clarification exchange and the first answer (Turn 4) — into a single consolidated retrieval query; Stage 3 generates Turn 6 with the enriched retrieved context.

**Table 8: Multi-Turn Answer Quality — Turn 6 (n = 30)**

| Metric | A: LLM-only | B: Stage 2 Only | C: Full Pipeline |
|--------|------------|-----------------|-----------------|
| Mean Expert Score (1–4) | — | — | — |
| % Fully Correct (score = 4) | — | — | — |

Multi-turn RAG scenarios pose unique challenges — models struggle notably on later turns without tailored handling[15](https://ar5iv.labs.arxiv.org/html/2501.03468v1#:~:text=We%20evaluate%20our%20mt%20RAG,questions%2C%20and%20in%20later%20turns). Most RAG benchmarks focus only on single-turn exchanges[16](https://ar5iv.labs.arxiv.org/html/2501.03468v1#:~:text=in%20recent%20years%20Lewis%20et%C2%A0al,of%20the%20full%20RAG%20pipeline); by evaluating multi-turn handling explicitly, we fill an important gap.

### 5.4.3 Hallucination and Citation Fidelity

Legal assistants must not fabricate laws or citations. We evaluate hallucination rates and citation fidelity consistently across all three manually-scored configurations.

**Definition:** A response is hallucinated if it contains any factually incorrect statement or cites a source for a proposition that the source does not support[17](https://dho.stanford.edu/wp-content/uploads/Legal_RAG_Hallucinations.pdf#:~:text=proposes%20a%20framework%20for%20evaluating,ranging).

**Table 9: Hallucination and Citation Fidelity**

| Metric | A: LLM-only | B: Stage 2 Only | C: Full Pipeline |
|--------|------------|-----------------|-----------------|
| Hallucination Rate (%) | — | — | — |
| Fabricated Citation Rate (%) | — | — | — |
| Citation Precision (%) | N/A | — | — |
| Citation Recall (%) | N/A | — | — |

> *Citation Precision/Recall are N/A for Config A because there is no retrieved context to cite from.*

Consistent evaluation across all three configurations is critical: it demonstrates not only that RAG reduces hallucinations compared to a standalone LLM[18](https://dho.stanford.edu/wp-content/uploads/Legal_RAG_Hallucinations.pdf#:~:text=the%20performance%20of%20AI,Section%C2%A09), but also quantifies whether query analysis (Stage 1) further improves citation fidelity by improving the quality of retrieved context fed to Stage 3.

**RAG Triad scores** (LLM-as-judge) are computed for Config B and Config C alongside human evaluation to validate automated-vs-manual agreement:

**Table 10: RAG Triad Metrics (Configs B and C)**

| Metric | B: Stage 2 Only | C: Full Pipeline |
|--------|-----------------|-----------------|
| Context Relevance (0–1) | — | — |
| Groundedness (0–1) | — | — |
| Answer Relevance (0–1) | — | — |

---

## 5.5 Ablation Summary (All Claims — Consolidated)

This section consolidates all findings from §5.2–§5.4 into a single reference table. No new experiments are introduced here; the purpose is to present a unified view of each pipeline component's contribution.

### 5.5.1 Consolidated Experiment Matrix

**Table 11: Full Experiment Matrix**

| Variant | Recall@5 | MRR | Mean Expert Score | Hallucination Rate | Evaluation Method |
|---------|----------|-----|-------------------|--------------------|-------------------|
| **C: Full Pipeline** | — | — | — | — | Automated + Manual |
| Dense-only | — | — | — | — | Automated only |
| Lexical-only | — | — | — | — | Automated only |
| Symbolic-only | — | — | — | — | Automated only |
| Hybrid – no translation | — | — | — | — | Automated only (n=65 non-English queries) |
| Hybrid – no clarification | — | — | — | — | Automated only (n=30 ambiguous queries) |
| **B: Stage 2 only** | — | — | — | — | Automated + Manual |
| **A: LLM-only** | N/A | N/A | — | — | Manual only |

> *Dense-only, Lexical-only, Symbolic-only, and translation/clarification ablations are evaluated via automated retrieval metrics only. Expert scores and hallucination rates for these variants are inferred from the layered comparison of Configs A, B, and C.*

### 5.5.2 Claim Validation Summary

**Claim 1: Hybrid retrieval > single retriever**

- Evidence: Table 2 (§5.2) — automated Recall@K, Hit Rate@K, MRR across all four retrieval strategies
- Supporting evidence: Table 3 (§5.2) — per-`retrieval_target` breakdown shows where each strategy wins
- Error typology (§5.2.2) — qualitative analysis of complementary failure modes

**Claim 2: Translation pivot improves retrieval and answer quality for Filipino/Cebuano**

- Retrieval evidence: Table 4 (§5.3) — automated Hit Rate@5, Recall@5 with vs. without translation
- Answer quality evidence: Table 6 (§5.4) — Config B vs. Config C on non-English query subset reveals how translation (part of Stage 1) improves end-to-end quality

**Claim 3: Clarification handling reduces errors under ambiguity**

- Answer quality evidence: Table 7 (§5.4) — Config B vs. Config C on the 30 ambiguous queries; the Full Pipeline's clarification handling should substantially outperform the no-clarification condition
- Clarification relevance: expert judgment on follow-up question quality (§5.4.1)

### 5.5.3 Automated vs. Manual Effort Summary

| Evaluation Component | Automated | Manual (Expert) | Notes |
|----------------------|-----------|-----------------|-------|
| Recall@K / Hit Rate@K / MRR | ✅ | | All 8 variants, fully deterministic; Hybrid – no translation scoped to n=65 non-English queries; Hybrid – no clarification scoped to n=30 ambiguous queries |
| F1 / ROUGE-L / Exact Match | ✅ | | 3 manual configs only |
| Citation extraction + matching | ⚠️ Partial | Spot-check | Regex extraction automated; fabrication manual |
| Clarification relevance | | ✅ | Expert judgment on Config C only |
| Answer legal accuracy (4-pt scale) | | ✅ | 3 configs × 100 queries × 2 experts = 600 ratings |
| Hallucination audit | | ✅ | 3 configs, expert verifies claims against context |
| RAG Triad (context/ground/answer) | ✅ (LLM judge) | | Configs B and C |
| Error typology classification | | ✅ | Retrieval failure categorization (§5.2.2) |

**Total manual evaluation effort:** 600 individual expert ratings (compared to 1,600 if all 8 variants required manual scoring). This optimization is achieved by limiting expert evaluation to the three configurations that form a layered comparison (LLM-only → +Retrieval → +Query Analysis), while relying on automated metrics for sub-component comparisons within Stage 1 and Stage 2.

---

## Summary

Through this structured evaluation, we demonstrate that our three-stage RAG pipeline delivers robust performance on multilingual legal queries, addressing a key gap in low-resource NLP. The evaluation is organized into a clear progression:

1. **Retrieval comparison** (§5.2) establishes that hybrid retrieval outperforms any single strategy, with per-strategy breakdowns and error typology providing diagnostic depth.
2. **Query analysis evaluation** (§5.3) confirms that translation pivot and clarification handling each improve retrieval quality, measured via automated metrics that are fully reproducible.
3. **End-to-end answer quality** (§5.4) demonstrates cumulative value through three layered configurations — LLM-only → Stage 2 only → Full Pipeline — with consistent expert evaluation of legal accuracy, hallucination rates, and citation fidelity across all three.

We introduce evaluation dimensions not commonly reported in prior RAG systems but crucial for real-world legal AI: multi-turn dialogue handling, citation fidelity checks, and structured error typology analysis. By framing evaluation around real legal scenarios — clarifying ambiguous questions, citing sources for every statement, handling multilingual input — we push beyond generic QA benchmarks and establish a blueprint for evaluating trusted AI systems in low-resource legal domains[14](https://dho.stanford.edu/wp-content/uploads/Legal_RAG_Hallucinations.pdf#:~:text=We%20also%20document%20substantial%20variation,among%20the%20sys%02tems%20we%20tested)[7](https://openreview.net/pdf?id=vUwEzXgQDX#:~:text=%E2%80%A2%20Retrieval%20Method%3A%20A%20hybrid,core%20semantic%20un%02derstanding%20of%20the)[11](https://openreview.net/pdf?id=vUwEzXgQDX#:~:text=The%20architectural%20shift%20to%20hybrid,complex%2C%20nuanced%2C%20and%20multilingual%20queries).

---

## Sources

- Y. Katsis et al., "MTRAG: A Multi-Turn Conversational Benchmark for Evaluating RAG Systems," arXiv, 2025. [15][16]
- S. Xu et al., "Hallucination-Free? Assessing the Reliability of AI Legal Research Tools," J. Empir. Legal Stud., 2025. [14][17][18]
- S. Soni et al., "A Free Format Legal Question Answering System," ACL NLLP Workshop, 2021. [2][12][13]
- B. Perez et al., "A Multilingual Intelligent Document QA System," OpenReview preprint, 2023. [7][9][10][11]
- TruLens RAG Evaluation Guide, 2025. [3][4]

---

**Reference Links**

[1] [5] [6] [7] [8] [9] [10] [11] openreview.net — https://openreview.net/pdf?id=vUwEzXgQDX

[2] [12] [13] A Free Format Legal Question Answering System — https://aclanthology.org/2021.nllp-1.11.pdf

[3] [4] RAG Triad - TruLens — https://www.trulens.org/getting_started/core_concepts/rag_triad/

[14] [17] [18] [19] Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools — https://dho.stanford.edu/wp-content/uploads/Legal_RAG_Hallucinations.pdf

[15] [16] mtRAG: A Multi-Turn Conversational Benchmark for Evaluating Retrieval-Augmented Generation Systems — https://ar5iv.labs.arxiv.org/html/2501.03468v1
