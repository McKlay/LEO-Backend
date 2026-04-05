"""
Retrieval performance metrics (Recall@K, Hit Rate@K, MRR).

Usage::

    from tests.benchmark.scorers.retrieval import score_retrieval
    scores = score_retrieval(trace, k_values=[3, 5, 10])
    # → {"recall@3": 0.5, "recall@5": 1.0, "hit_rate@3": 1, ..., "mrr": 0.5}
"""
from __future__ import annotations

from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from tests.benchmark.collector import QueryTrace

# ── Default K values ──────────────────────────────────────────────────────────
DEFAULT_K_VALUES: List[int] = [3, 5, 10]


def normalize_chunk_id(chunk_id: str) -> str:
    """
    Normalise a chunk identifier for consistent comparison.

    Chunk identifiers are the canonical ``chunk_id`` values declared in each
    chunk's YAML frontmatter and stored in ``metadata.chunk_id`` in the vector
    store (e.g. ``dole_handbook_2023_min_wage_eemr_formulas``,
    ``RA-11058-06``, ``ra-11199-14-sec29-33-final-provisions``).
    Gold chunks in ``benchmark-queries.json`` use the same identifiers.

    The only transformation required is lowercasing — chunk_ids use mixed
    conventions (snake_case, kebab-case, UPPER-kebab) across document sets.

    Args:
        chunk_id: Raw chunk identifier string.

    Returns:
        Lowercased string suitable for equality comparison.
    """
    return chunk_id.strip().lower()


def recall_at_k(
    gold_chunks: List[str],
    retrieved_ids: List[str],
    k: int,
) -> float:
    """
    Compute Recall@K: fraction of gold chunks present in the top-K results.

    ``Recall@K = |gold ∩ retrieved[:K]| / |gold|``

    Args:
        gold_chunks: Ground-truth chunk identifiers.
        retrieved_ids: Retrieved chunk IDs ranked by score (descending).
        k: Cut-off position.

    Returns:
        Float in [0, 1].  Returns 0.0 if *gold_chunks* is empty.
    """
    if not gold_chunks:
        return 0.0

    gold_norm = {normalize_chunk_id(c) for c in gold_chunks}
    top_k_norm = {normalize_chunk_id(c) for c in retrieved_ids[:k]}
    return len(gold_norm & top_k_norm) / len(gold_norm)


def hit_rate_at_k(
    gold_chunks: List[str],
    retrieved_ids: List[str],
    k: int,
) -> int:
    """
    Compute Hit Rate@K: binary indicator of whether *any* gold chunk appears
    in the top-K results.

    Args:
        gold_chunks: Ground-truth chunk identifiers.
        retrieved_ids: Retrieved chunk IDs ranked by score (descending).
        k: Cut-off position.

    Returns:
        1 if at least one gold chunk is in top-K, else 0.
    """
    if not gold_chunks:
        return 0

    gold_norm = {normalize_chunk_id(c) for c in gold_chunks}
    for cid in retrieved_ids[:k]:
        if normalize_chunk_id(cid) in gold_norm:
            return 1
    return 0


def mrr(gold_chunks: List[str], retrieved_ids: List[str]) -> float:
    """
    Compute Mean Reciprocal Rank (MRR) for a single query.

    ``MRR = 1 / rank_of_first_gold_chunk``  (0.0 if no gold chunk found)

    Args:
        gold_chunks: Ground-truth chunk identifiers.
        retrieved_ids: Retrieved chunk IDs ranked by score (descending).

    Returns:
        Float in (0, 1].  Returns 0.0 if no gold chunk appears in the list
        or if *gold_chunks* is empty.
    """
    if not gold_chunks:
        return 0.0

    gold_norm = {normalize_chunk_id(c) for c in gold_chunks}
    for rank, cid in enumerate(retrieved_ids, start=1):
        if normalize_chunk_id(cid) in gold_norm:
            return 1.0 / rank
    return 0.0


def score_retrieval(
    trace: "QueryTrace",
    k_values: List[int] = DEFAULT_K_VALUES,
) -> Dict[str, float]:
    """
    Compute all retrieval metrics for a single ``QueryTrace``.

    Uses ``trace.retrieved_chunk_ids_per_k`` for per-K metrics, issuing one
    lookup per K value (RRF-correct: no slicing of a larger pool). MRR is
    computed from the max-K list for the broadest rank-position coverage.

    Args:
        trace: A finalised ``QueryTrace`` with ``retrieved_chunk_ids_per_k``
               and ``gold_chunks`` populated.
        k_values: List of cut-off positions.  Defaults to [3, 5, 10].

    Returns:
        Dict with keys ``recall@K``, ``hit_rate@K`` (for each K) and ``mrr``.
        If ``gold_chunks`` is empty or ``retrieved_chunk_ids_per_k`` is empty,
        all values are 0.0 / 0.
    """
    gold = trace.gold_chunks or []
    per_k = trace.retrieved_chunk_ids_per_k or {}

    scores: Dict[str, float] = {}
    for k in k_values:
        retrieved = per_k.get(k, [])
        scores[f"recall@{k}"] = recall_at_k(gold, retrieved, k)
        scores[f"hit_rate@{k}"] = float(hit_rate_at_k(gold, retrieved, k))

    # MRR uses the max-K list for the broadest rank-position coverage.
    max_retrieved = per_k.get(max(k_values), []) if per_k else []
    scores["mrr"] = mrr(gold, max_retrieved)
    return scores

