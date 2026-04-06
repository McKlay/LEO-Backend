"""
Citation accuracy metrics: extraction, normalisation, precision, and recall.

Compares machine-extracted citations from ``trace.generated_response``
against ``trace.gold_article_refs`` from the benchmark dataset.

Supported citation forms (case-insensitive):
- Labor Code articles: ``Article 297``, ``Art. 297``, ``Art 297``, ``Artikulo 297``
- Republic Acts: ``RA 6727``, ``Republic Act No. 6727``, ``R.A. 6727``
- Presidential Decrees: ``PD 442``, ``Presidential Decree No. 442``, ``P.D. 442``
- Wage Orders: ``Wage Order NCR-24``, ``NCR-24``
- DOLE Department Orders: ``Department Order No. 174``, ``DO No. 174``, ``D.O. 174``

Usage::

    from tests.benchmark.scorers.citation import score_citations
    scores = score_citations(trace)
    # → {"citation_precision": 0.8, "citation_recall": 1.0,
    #    "citation_f1": 0.89, "extracted_count": 5, "gold_count": 4}
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from tests.benchmark.collector import QueryTrace


# ── Regex patterns ─────────────────────────────────────────────────────────────

# Article references (Labor Code, Civil Code, etc.)
_RE_ARTICLE = re.compile(
    r"\b(?:Art(?:icle|\.)?|Artikulo)\s*\.?\s*(\d+(?:-[A-Z])?)",
    re.IGNORECASE,
)

# Republic Acts
_RE_RA = re.compile(
    r"\b(?:Republic\s+Act\s+(?:No\.?\s*)?|R\.?A\.?\s*(?:No\.?\s*)?)(\d+)",
    re.IGNORECASE,
)

# Presidential Decrees
_RE_PD = re.compile(
    r"\b(?:Presidential\s+Decree\s+(?:No\.?\s*)?|P\.?D\.?\s*(?:No\.?\s*)?)(\d+)",
    re.IGNORECASE,
)

# DOLE Department / Labor Department Orders
_RE_DO = re.compile(
    r"\b(?:Department\s+Order\s+(?:No\.?\s*)?|D\.?O\.?\s*(?:No\.?\s*)?)(\d+(?:-[A-Z])?)",
    re.IGNORECASE,
)

# Wage Orders (e.g., "Wage Order NCR-24", "NCR-24")
_RE_WO = re.compile(
    r"\bWage\s+Order\s+((?:NCR|R[IVX]+)-\d+)\b",
    re.IGNORECASE,
)

# ── Extraction ─────────────────────────────────────────────────────────────────

def extract_citations(text: str) -> List[str]:
    """
    Extract all statutory citation strings from *text*.

    Returns raw matched strings (not yet normalised).  Duplicates are
    preserved; call :func:`normalize_citation` on each result before
    comparison.

    Args:
        text: Generated answer text (plain or markdown).

    Returns:
        List of raw citation strings in order of appearance.
    """
    citations: List[str] = []

    for m in _RE_ARTICLE.finditer(text):
        citations.append(f"Article {m.group(1)}")

    for m in _RE_RA.finditer(text):
        citations.append(f"RA {m.group(1)}")

    for m in _RE_PD.finditer(text):
        citations.append(f"PD {m.group(1)}")

    for m in _RE_DO.finditer(text):
        citations.append(f"DO {m.group(1)}")

    for m in _RE_WO.finditer(text):
        citations.append(f"Wage Order {m.group(1).upper()}")

    return citations


# ── Normalisation ──────────────────────────────────────────────────────────────

def normalize_citation(citation: str) -> str:
    """
    Canonicalise a citation string for equality comparison.

    Transformations applied:
    - ``Art. 297`` / ``Art 297`` / ``Artikulo 297`` → ``article 297``
    - ``Republic Act No. 6727`` / ``R.A. 6727`` → ``ra 6727``
    - ``Presidential Decree No. 442`` / ``P.D. 442`` → ``pd 442``
    - ``Department Order No. 174`` / ``D.O. 174`` → ``do 174``
    - ``Wage Order NCR-24`` → ``wage order ncr-24``

    Comparison is therefore always lowercase and uses short canonical prefixes.

    Args:
        citation: Raw or pre-extracted citation string.

    Returns:
        Normalised lowercase string.
    """
    c = citation.strip().lower()

    # Normalize article references
    c = re.sub(
        r"\b(?:art(?:icle|\.)?|artikulo)\s*\.?\s*(\d+(?:-[a-z])?)",
        lambda m: f"article {m.group(1)}",
        c,
        flags=re.IGNORECASE,
    )

    # Normalize Republic Acts
    c = re.sub(
        r"\b(?:republic\s+act\s+(?:no\.?\s*)?|r\.?a\.?\s*(?:no\.?\s*)?)(\d+)",
        lambda m: f"ra {m.group(1)}",
        c,
        flags=re.IGNORECASE,
    )

    # Normalize Presidential Decrees
    c = re.sub(
        r"\b(?:presidential\s+decree\s+(?:no\.?\s*)?|p\.?d\.?\s*(?:no\.?\s*)?)(\d+)",
        lambda m: f"pd {m.group(1)}",
        c,
        flags=re.IGNORECASE,
    )

    # Normalize Department Orders
    c = re.sub(
        r"\b(?:department\s+order\s+(?:no\.?\s*)?|d\.?o\.?\s*(?:no\.?\s*)?)(\d+(?:-[a-z])?)",
        lambda m: f"do {m.group(1)}",
        c,
        flags=re.IGNORECASE,
    )

    # Collapse excess whitespace
    c = re.sub(r"\s+", " ", c).strip()
    return c


def _normalize_set(citations: List[str]) -> Set[str]:
    """Return deduplicated set of normalised citation strings."""
    return {normalize_citation(c) for c in citations if c.strip()}


# ── Scoring functions ──────────────────────────────────────────────────────────

def citation_precision(extracted: List[str], gold: List[str]) -> float:
    """
    Fraction of extracted citations that appear in the gold set.

    ``precision = |extracted_norm ∩ gold_norm| / |extracted_norm|``

    Args:
        extracted: Citations extracted from the generated answer.
        gold: Gold-standard citation references.

    Returns:
        Float in [0, 1].  Returns 0.0 if *extracted* is empty.
    """
    if not extracted:
        return 0.0
    ext_norm = _normalize_set(extracted)
    gold_norm = _normalize_set(gold)
    if not ext_norm:
        return 0.0
    return len(ext_norm & gold_norm) / len(ext_norm)


def citation_recall(extracted: List[str], gold: List[str]) -> float:
    """
    Fraction of gold citations that were found in the generated answer.

    ``recall = |extracted_norm ∩ gold_norm| / |gold_norm|``

    Args:
        extracted: Citations extracted from the generated answer.
        gold: Gold-standard citation references.

    Returns:
        Float in [0, 1].  Returns 0.0 if *gold* is empty.
    """
    if not gold:
        return 0.0
    gold_norm = _normalize_set(gold)
    if not gold_norm:
        return 0.0
    ext_norm = _normalize_set(extracted)
    return len(ext_norm & gold_norm) / len(gold_norm)


def citation_f1(precision: float, recall: float) -> float:
    """Harmonic mean of citation precision and recall."""
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


# ── Trace-level scorer ─────────────────────────────────────────────────────────

def score_citations(trace: "QueryTrace") -> Dict[str, float]:
    """
    Compute citation precision, recall, and F1 for a single ``QueryTrace``.

    Extracts citations from ``trace.generated_response`` (free text) and
    compares against ``trace.gold_article_refs``.

    Also considers citations from ``trace.generated_citations`` (structured
    pipeline output) as an additional extraction source.

    Args:
        trace: A finalised ``QueryTrace``.

    Returns:
        Dict with keys ``citation_precision``, ``citation_recall``,
        ``citation_f1``, ``extracted_count``, ``gold_count``.
        All metric values are 0.0 if there are no gold references.
    """
    gold = trace.gold_article_refs or []
    content = trace.generated_response or ""

    # Extract from plain text
    text_citations = extract_citations(content)

    # Also harvest structured citations produced by the pipeline
    structured: List[str] = []
    for cit in trace.generated_citations or []:
        if isinstance(cit, dict):
            # Try common field names used by the pipeline
            for key in ("article", "statute", "reference", "title", "citation"):
                val = cit.get(key, "")
                if val:
                    structured.append(str(val))
                    break
        elif isinstance(cit, str):
            structured.append(cit)

    all_extracted = text_citations + structured

    p = citation_precision(all_extracted, gold)
    r = citation_recall(all_extracted, gold)

    return {
        "citation_precision": p,
        "citation_recall": r,
        "citation_f1": citation_f1(p, r),
        "extracted_count": len(_normalize_set(all_extracted)),
        "gold_count": len(_normalize_set(gold)),
    }

