"""
Reciprocal Rank Fusion (RRF) for hybrid retrieval result merging.

Implements the RRF algorithm (Cormack, Clarke & Buettcher, 2009) to merge
ranked results from multiple independent retrieval strategies (symbolic,
lexical, dense) into a single coherent ranking.

RRF is distinct from post-retrieval reranking (cross-encoder models):
- RRF merges *parallel* strategy outputs using only list-position, no extra model.
- Cross-encoder reranking (retrieve_with_reranking stub) rescores an already-
  retrieved set with a heavier model — a separate future feature.
"""
from typing import Dict, List
from collections import defaultdict

from adapters.vectorstore.base import QueryResult
from core import get_logger

logger = get_logger(__name__)


def reciprocal_rank_fusion(
    ranked_lists: Dict[str, List[QueryResult]],
    k: int = 60,
) -> List[QueryResult]:
    """
    Merge N strategy-ranked lists via Reciprocal Rank Fusion.

    score(d) = Σ_s  1 / (k + rank_s(d))

    where rank_s(d) is the 1-based position of document d in strategy s's list.
    Documents absent from a strategy contribute 0 from that strategy (no penalty).
    k=60 is the empirically validated default (Cormack et al. 2009).

    Args:
        ranked_lists: Mapping of strategy name → best-first list of QueryResults.
                      Empty lists are silently skipped.
        k: RRF smoothing constant. Higher k reduces the rank-position advantage of
           top-ranked documents. Default 60.

    Returns:
        Single merged list sorted by RRF score descending.
        Each result's ``score`` field is set to its RRF score.
        Observability fields added to ``metadata``:
          - ``_rrf_score``             : float — final RRF score
          - ``_contributing_strategies``: list[str] — strategies that returned this doc
          - ``_strategy_ranks``         : dict[str, int] — per-strategy 1-based rank
    """
    active = {s: lst for s, lst in ranked_lists.items() if lst}
    if not active:
        return []

    # Accumulate RRF scores and per-strategy rank info keyed by document ID
    rrf_scores: Dict[str, float] = defaultdict(float)
    doc_strategy_ranks: Dict[str, Dict[str, int]] = defaultdict(dict)
    canonical: Dict[str, QueryResult] = {}  # first-seen instance per doc ID

    for strategy, lst in active.items():
        for rank, result in enumerate(lst, start=1):
            doc_id = result.id
            rrf_scores[doc_id] += 1.0 / (k + rank)
            doc_strategy_ranks[doc_id][strategy] = rank
            if doc_id not in canonical:
                canonical[doc_id] = result

    # Build output list with RRF metadata attached
    merged: List[QueryResult] = []
    for doc_id, rrf_score in rrf_scores.items():
        src = canonical[doc_id]
        ranks = doc_strategy_ranks[doc_id]
        contributing = sorted(ranks.keys())

        updated_meta = dict(src.metadata)
        updated_meta.update({
            "_rrf_score": rrf_score,
            "_contributing_strategies": contributing,
            "_strategy_ranks": ranks,
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
    logger.debug(
        f"RRF merged {len(merged)} docs from strategies {sorted(active.keys())}, "
        f"k={k}, cross-strategy agreements={cross_strategy_count}"
    )

    return merged
