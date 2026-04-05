"""
Clarification detection metrics: precision, recall, and F1.

Treats clarification detection as a binary classification task:
- **Positive**: the system needs to ask a clarifying question.
- **Negative**: the query is clear enough to answer directly.

For ambiguous queries in the benchmark (``is_ambiguous=True``),
``expected_clarification`` is a non-empty string; for clear queries it
is ``None`` or ``""``.  The system's prediction is ``trace.needs_clarification``.

Usage::

    from tests.benchmark.scorers.clarification import (
        score_clarification, aggregate_clarification
    )

    # Per-trace
    result = score_clarification(trace)
    # → {"predicted": True, "expected": True, "outcome": "TP", "tp": 1, ...}

    # Multi-trace aggregate
    agg = aggregate_clarification(traces)
    # → {"precision": 0.9, "recall": 0.87, "f1": 0.88,
    #    "tp": 26, "fp": 3, "fn": 4, "tn": 17, "total": 50}
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from tests.benchmark.collector import QueryTrace

# Clarification detection P/R is a pre-flight diagnostic only (Decision 1).
# It must NOT appear in thesis-table output or the raw-results CSV.
IS_THESIS_TABLE = False


# ── Per-trace scoring ──────────────────────────────────────────────────────────

def score_clarification(trace: "QueryTrace") -> Dict[str, Any]:
    """
    Evaluate clarification detection for a single ``QueryTrace``.

    "Expected positive" is determined by whether ``trace.expected_clarification``
    is a non-empty string (benchmark-labelled ambiguous queries always have one).

    Args:
        trace: A ``QueryTrace`` with ``needs_clarification`` and
               ``expected_clarification`` fields populated.

    Returns:
        Dict with keys:
        - ``predicted`` (bool | None): system's ``needs_clarification`` flag.
        - ``expected`` (bool): ground-truth label from benchmark.
        - ``outcome`` (str): one of ``"TP"``, ``"FP"``, ``"FN"``, ``"TN"``,
          or ``"unknown"`` if prediction is None.
        - ``tp``, ``fp``, ``fn``, ``tn`` (int): single-trace confusion counts.
    """
    expected_pos: bool = bool(trace.expected_clarification)
    predicted: Optional[bool] = trace.needs_clarification

    if predicted is None:
        return {
            "predicted": None,
            "expected": expected_pos,
            "outcome": "unknown",
            "tp": 0, "fp": 0, "fn": 0, "tn": 0,
        }

    if predicted and expected_pos:
        outcome = "TP"
        tp, fp, fn, tn = 1, 0, 0, 0
    elif predicted and not expected_pos:
        outcome = "FP"
        tp, fp, fn, tn = 0, 1, 0, 0
    elif not predicted and expected_pos:
        outcome = "FN"
        tp, fp, fn, tn = 0, 0, 1, 0
    else:
        outcome = "TN"
        tp, fp, fn, tn = 0, 0, 0, 1

    return {
        "predicted": predicted,
        "expected": expected_pos,
        "outcome": outcome,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


# ── Aggregate scoring ──────────────────────────────────────────────────────────

def aggregate_clarification(traces: List["QueryTrace"]) -> Dict[str, Any]:
    """
    Compute aggregate clarification detection metrics over a collection of traces.

    Only traces with a non-``None`` ``needs_clarification`` prediction are counted.

    Args:
        traces: List of ``QueryTrace`` objects (typically the 50 validation
                queries: 30 ambiguous + 20 clear).

    Returns:
        Dict with keys:
        - ``precision``, ``recall``, ``f1`` (float).
        - ``tp``, ``fp``, ``fn``, ``tn`` (int): aggregate confusion matrix cells.
        - ``total`` (int): number of traces scored (excluding unknowns).
        - ``skipped`` (int): traces skipped (``needs_clarification`` was None).
    """
    tp = fp = fn = tn = skipped = 0

    for trace in traces:
        result = score_clarification(trace)
        if result["outcome"] == "unknown":
            skipped += 1
            continue
        tp += result["tp"]
        fp += result["fp"]
        fn += result["fn"]
        tn += result["tn"]

    total = tp + fp + fn + tn

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "total": total,
        "skipped": skipped,
    }

