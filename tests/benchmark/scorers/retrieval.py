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

    Handles two canonical forms used in this project:
    - Source-path form: ``DOLE-Handbook/02-minimum-wage.md``  (gold chunks)
    - Metadata-constructed form: identical path built by ResultCollector

    Steps:
    1. Strip ``kb/chunks/`` or ``kb\\chunks\\`` prefix (some paths carry it).
    2. Normalise path separators to ``/``.
    3. Lowercase the whole string.

    Args:
        chunk_id: Raw chunk identifier string.

    Returns:
        Normalised string suitable for equality comparison.
    """
    chunk_id = chunk_id.replace("\\", "/")
    for prefix in ("kb/chunks/", "kb/"):
        if chunk_id.lower().startswith(prefix):
            chunk_id = chunk_id[len(prefix):]
            break
    return chunk_id.lower()


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

    Slices ``trace.retrieved_chunk_ids`` at each K to compute per-K metrics.
    A single retrieval call at ``max(K)`` therefore yields metrics for all
    smaller K values without additional pipeline calls.

    Args:
        trace: A finalised ``QueryTrace`` with ``retrieved_chunk_ids`` and
               ``gold_chunks`` populated.
        k_values: List of cut-off positions.  Defaults to [3, 5, 10].

    Returns:
        Dict with keys ``recall@K``, ``hit_rate@K`` (for each K) and ``mrr``.
        If ``gold_chunks`` is empty or ``retrieved_chunk_ids`` is empty,
        all values are 0.0 / 0.
    """
    gold = trace.gold_chunks or []
    retrieved = trace.retrieved_chunk_ids or []

    scores: Dict[str, float] = {}
    for k in k_values:
        scores[f"recall@{k}"] = recall_at_k(gold, retrieved, k)
        scores[f"hit_rate@{k}"] = float(hit_rate_at_k(gold, retrieved, k))

    scores["mrr"] = mrr(gold, retrieved)
    return scores

