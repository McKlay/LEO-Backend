"""
Reciprocal Rank Fusion (RRF) for hybrid retrieval result merging.

Implements the **weighted** RRF algorithm (extended from Cormack, Clarke &
Buettcher, 2009) to merge ranked results from multiple independent retrieval
strategies (symbolic, lexical, dense) into a single coherent ranking.

Standard RRF treats every strategy equally, which causes *rank dilution* when
two weak strategies agree on a wrong document and outvote the one strategy that
found the correct answer.  Strategy-specific weights solve this:

    score(d) = Σ_s  w_s / (k + rank_s(d))

Phase-1 benchmark evidence (100 queries, 3 languages):
    dense   → Recall@5 = 0.845, HR@5 = 0.98   → w = 2.0
    lexical → Recall@5 = 0.837, HR@5 = 0.93   → w = 1.0
    symbolic→ Recall@5 = 0.439, HR@5 = 0.51   → w = 0.5

With these defaults a dense rank-1 hit (0.0328) beats lexical+symbolic rank-1
noise (0.0164 + 0.0082 = 0.0246), directly mitigating the 13-query dilution
problem identified in Phase 1.

RRF is distinct from post-retrieval reranking (cross-encoder models):
- RRF merges *parallel* strategy outputs using only list-position, no extra model.
- Cross-encoder reranking (retrieve_with_reranking stub) rescores an already-
  retrieved set with a heavier model — a separate future feature.
"""
from typing import Dict, List, Optional
from collections import defaultdict

from adapters.vectorstore.base import QueryResult
from core import get_logger

logger = get_logger(__name__)

# Default strategy weights derived from Phase-1 retrieval benchmark.
# Dense is the single strongest strategy (HR@5=0.98, Recall@5=0.845);
# lexical is a strong complement; symbolic is supplementary.
DEFAULT_STRATEGY_WEIGHTS: Dict[str, float] = {
    "dense": 2.0,
    "lexical": 1.0,
    "symbolic": 0.5,
}


def reciprocal_rank_fusion(
    ranked_lists: Dict[str, List[QueryResult]],
    k: int = 60,
    weights: Optional[Dict[str, float]] = None,
) -> List[QueryResult]:
    """
    Merge N strategy-ranked lists via **weighted** Reciprocal Rank Fusion.

    score(d) = Σ_s  w_s / (k + rank_s(d))

    where rank_s(d) is the 1-based position of document d in strategy s's list
    and w_s is the strategy weight (default 1.0 for unknown strategies).
    Documents absent from a strategy contribute 0 from that strategy (no penalty).
    k=60 is the empirically validated default (Cormack et al. 2009).

    Args:
        ranked_lists: Mapping of strategy name → best-first list of QueryResults.
                      Empty lists are silently skipped.
        k: RRF smoothing constant. Higher k reduces the rank-position advantage of
           top-ranked documents. Default 60.
        weights: Optional mapping of strategy name → weight multiplier.
                 Strategies not in the dict default to 1.0.
                 Pass ``None`` to use :data:`DEFAULT_STRATEGY_WEIGHTS`.

    Returns:
        Single merged list sorted by RRF score descending.
        Each result's ``score`` field is set to its weighted RRF score.
        Observability fields added to ``metadata``:
          - ``_rrf_score``             : float — final weighted RRF score
          - ``_contributing_strategies``: list[str] — strategies that returned this doc
          - ``_strategy_ranks``         : dict[str, int] — per-strategy 1-based rank
          - ``_strategy_weights``       : dict[str, float] — per-strategy weight used
    """
    active = {s: lst for s, lst in ranked_lists.items() if lst}
    if not active:
        return []

    effective_weights = weights if weights is not None else DEFAULT_STRATEGY_WEIGHTS

    # Accumulate RRF scores and per-strategy rank info keyed by document ID.
    #
    # Section-aware deduplication: chunks from labor_law_chunks carry their parent
    # section's UUID in metadata['section_id'].  Lexical search returns sections
    # directly (no section_id in metadata).  By normalising chunk doc_ids to the
    # parent section UUID, a dense chunk result and a lexical section result for the
    # same document now share the same key and contribute a *combined* RRF score.
    # Without this, large handbook sections that have chunks never benefit from
    # cross-strategy fusion because the chunk UUID ≠ the section UUID.
    #
    # Within each strategy we take only the BEST (lowest) rank per section to avoid
    # triple-counting sections that have multiple high-ranking chunks.
    rrf_scores: Dict[str, float] = defaultdict(float)
    doc_strategy_ranks: Dict[str, Dict[str, int]] = defaultdict(dict)
    doc_strategy_weights: Dict[str, Dict[str, float]] = defaultdict(dict)
    canonical: Dict[str, QueryResult] = {}  # first-seen instance per doc ID

    for strategy, lst in active.items():
        w = effective_weights.get(strategy, 1.0)
        # Track the best (lowest) rank seen per section within this strategy.
        best_rank_per_section: Dict[str, int] = {}
        for rank, result in enumerate(lst, start=1):
            # Normalise: chunk results expose their parent section UUID via
            # metadata['section_id']; section results have no such key.
            doc_id: str = result.metadata.get('section_id') or result.id
            if doc_id in best_rank_per_section:
                continue  # only count best (first) occurrence per section
            best_rank_per_section[doc_id] = rank
            rrf_scores[doc_id] += w / (k + rank)
            doc_strategy_ranks[doc_id][strategy] = rank
            doc_strategy_weights[doc_id][strategy] = w
            if doc_id not in canonical:
                canonical[doc_id] = result

    # Build output list with RRF metadata attached
    merged: List[QueryResult] = []
    for doc_id, rrf_score in rrf_scores.items():
        src = canonical[doc_id]
        ranks = doc_strategy_ranks[doc_id]
        s_weights = doc_strategy_weights[doc_id]
        contributing = sorted(ranks.keys())

        updated_meta = dict(src.metadata)
        updated_meta.update({
            "_rrf_score": rrf_score,
            "_contributing_strategies": contributing,
            "_strategy_ranks": ranks,
            "_strategy_weights": s_weights,
        })

        merged.append(QueryResult(
            id=src.id,
            content=src.content,
            metadata=updated_meta,
            score=rrf_score,
        ))

    merged.sort(key=lambda r: r.score, reverse=True)

    cross_strategy_count = sum(
        1 for r in merged
        if len(r.metadata.get("_contributing_strategies", [])) > 1
    )
    weight_summary = {s: effective_weights.get(s, 1.0) for s in active}
    logger.debug(
        f"RRF merged {len(merged)} docs from strategies {sorted(active.keys())}, "
        f"k={k}, weights={weight_summary}, cross-strategy agreements={cross_strategy_count}"
    )

    return merged
