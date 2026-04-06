"""Answer quality metrics: Token F1, ROUGE-L, and Exact Match.

All metrics compare ``trace.generated_response`` against
``trace.reference_answer`` from the benchmark query set.

Usage::

    from tests.benchmark.scorers.answer_quality import score_answer
    scores = score_answer(trace)
    # → {"token_f1": 0.72, "rouge_l": 0.68, "exact_match": 0.0}
    # → None  (if trace has no reference_answer or no generated_response)
"""
from __future__ import annotations

import re
import string
from typing import Counter, Dict, List, Optional, TYPE_CHECKING

from rouge_score import rouge_scorer  # type: ignore[import]

if TYPE_CHECKING:
    from tests.benchmark.collector import QueryTrace

# Singleton ROUGE scorer instance (not thread-safe but fine for sequential use)
_rouge = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=False)


# ── Text normalisation ─────────────────────────────────────────────────────────

def normalize_text(text: str) -> str:
    """
    Normalise free text for token-level comparison.

    Steps:
    1. Lowercase.
    2. Remove punctuation (``string.punctuation`` set).
    3. Collapse whitespace.

    Args:
        text: Raw text string.

    Returns:
        Normalised string.
    """
    text = text.lower()
    text = text.translate(str.maketrans("", "", string.punctuation))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokenize(text: str) -> List[str]:
    return normalize_text(text).split()


# ── Individual metrics ─────────────────────────────────────────────────────────

def token_f1(prediction: str, reference: str) -> float:
    """
    Compute word-level token F1 between *prediction* and *reference*.

    Uses bag-of-words overlap (same as SQuAD evaluation script).

    ``F1 = 2 * precision * recall / (precision + recall)``

    Args:
        prediction: Generated answer text.
        reference: Gold reference answer text.

    Returns:
        F1 score in [0, 1].
    """
    pred_tokens = _tokenize(prediction)
    ref_tokens = _tokenize(reference)

    if not pred_tokens or not ref_tokens:
        return 0.0

    pred_counts = Counter(pred_tokens)
    ref_counts = Counter(ref_tokens)

    common = sum((pred_counts & ref_counts).values())
    if common == 0:
        return 0.0

    precision = common / len(pred_tokens)
    recall = common / len(ref_tokens)
    return 2 * precision * recall / (precision + recall)


def rouge_l(prediction: str, reference: str) -> float:
    """
    Compute ROUGE-L F-measure between *prediction* and *reference*.

    Uses the ``rouge-score`` library with stemming disabled to keep the
    metric language-agnostic (important for Filipino / Cebuano answers).

    Args:
        prediction: Generated answer text.
        reference: Gold reference answer text.

    Returns:
        ROUGE-L F-score in [0, 1].
    """
    if not prediction.strip() or not reference.strip():
        return 0.0
    scores = _rouge.score(reference, prediction)
    return scores["rougeL"].fmeasure


def exact_match(prediction: str, reference: str) -> float:
    """
    Compute Exact Match after whitespace and case normalisation.

    Returns 1.0 if the normalised strings are identical, else 0.0.

    Args:
        prediction: Generated answer text.
        reference: Gold reference answer text.

    Returns:
        1.0 or 0.0.
    """
    return 1.0 if normalize_text(prediction) == normalize_text(reference) else 0.0


# ── Trace-level scorer ─────────────────────────────────────────────────────────

def score_answer(trace: "QueryTrace") -> Optional[Dict[str, float]]:
    """
    Compute Token F1, ROUGE-L, and Exact Match for a single ``QueryTrace``.

    Args:
        trace: A finalised ``QueryTrace`` with ``generated_response`` and
               ``reference_answer`` populated.

    Returns:
        Dict with keys ``token_f1``, ``rouge_l``, ``exact_match``.
        Returns ``None`` if either ``generated_response`` or
        ``reference_answer`` is missing/empty.
    """
    prediction = (trace.generated_response or "").strip()
    reference = (trace.reference_answer or "").strip()

    if not prediction or not reference:
        return None

    return {
        "token_f1": token_f1(prediction, reference),
        "rouge_l": rouge_l(prediction, reference),
        "exact_match": exact_match(prediction, reference),
    }

