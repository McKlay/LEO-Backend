"""
RAG Triad evaluation using GPT-4.1 as an LLM judge.

Scores each query–variant pair on three dimensions drawn from the TRIAD
framework (Garg et al., 2023):

- **Context Relevance (CR)**: Do the retrieved chunks actually address the query?
- **Groundedness (G)**: Is the generated answer supported by the retrieved context?
- **Answer Relevance (AR)**: Does the answer directly address the user's query?

Each dimension is scored 1–5 by the evaluator LLM.
CR and G are skipped for the ``llm_only`` variant (no retrieval → no context).

Usage (programmatic)::

    scorer = RAGTriadScorer()
    scores = await scorer.score_trace(trace)
    # → {"context_relevance": 4, "groundedness": 5, "answer_relevance": 4}

Usage (CLI)::

    python -m tests.benchmark.scorers.rag_triad \\
        --input results/run_001 \\
        --output results/run_001/rag_triad \\
        --concurrency 5

"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import openai

from core.config import settings

if TYPE_CHECKING:
    from tests.benchmark.collector import QueryTrace

logger = logging.getLogger(__name__)

# ── Rubric prompts ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are an expert evaluator assessing a Philippine labor-law RAG chatbot.
Score the provided dimension on a 1–5 integer scale using the rubric given.
Respond with valid JSON only: {"score": <integer 1-5>, "reason": "<brief>"}
"""

_CR_PROMPT = """\
DIMENSION: Context Relevance
Assess whether the RETRIEVED CONTEXT provides information that directly helps
answer the USER QUERY.

Rubric:
1 – No retrieved context, or context is completely irrelevant (wrong topic).
2 – Context is tangentially related but does not address the query.
3 – Context is partially relevant; some chunks useful, others not.
4 – Context is mostly relevant; minor irrelevant content present.
5 – All retrieved context is directly relevant and sufficient for the query.

USER QUERY:
{query}

RETRIEVED CONTEXT (top chunks, truncated):
{context}

Respond with JSON: {{"score": <1-5>, "reason": "<≤30 words>"}}
"""

_G_PROMPT = """\
DIMENSION: Groundedness
Assess whether the ANSWER is fully supported by the PROVIDED CONTEXT.
Claims not found in the context count as fabrications.

Rubric:
1 – Answer mostly fabricated; little to no grounding in the context.
2 – Major claims unsupported by context; significant hallucination.
3 – Answer is partially grounded; notable unsupported claims remain.
4 – Answer is well-grounded with only minor unverifiable claims.
5 – Every claim in the answer is directly traceable to the provided context.

USER QUERY:
{query}

PROVIDED CONTEXT:
{context}

GENERATED ANSWER:
{answer}

Respond with JSON: {{"score": <1-5>, "reason": "<≤30 words>"}}
"""

_AR_PROMPT = """\
DIMENSION: Answer Relevance
Assess whether the ANSWER directly and completely addresses the USER QUERY.
Ignore factual accuracy; focus only on relevance and completeness.

Rubric:
1 – Answer is completely off-topic or refuses to address the query.
2 – Answer misunderstands the query or addresses a different question.
3 – Answer partially addresses the query; key aspects missing.
4 – Answer mostly addresses the query with minor omissions.
5 – Answer directly and completely addresses all aspects of the query.

USER QUERY:
{query}

GENERATED ANSWER:
{answer}

Respond with JSON: {{"score": <1-5>, "reason": "<≤30 words>"}}
"""

_MAX_CONTEXT_CHARS = 3000   # truncate context to control token cost
_MAX_ANSWER_CHARS = 2000


# ── Helper ─────────────────────────────────────────────────────────────────────

def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n…[truncated]"


# ── Scorer class ───────────────────────────────────────────────────────────────

class RAGTriadScorer:
    """
    Async LLM-as-judge scorer for the RAG Triad dimensions.

    Args:
        model: OpenAI model to use for evaluation (default: ``settings.openai_llm_model``).
        concurrency: Max simultaneous OpenAI calls (default 5).
        temperature: Sampling temperature for the judge (default 0.0 for determinism).
    """

    def __init__(
        self,
        model: Optional[str] = None,
        concurrency: int = 5,
        temperature: float = 0.0,
    ) -> None:
        self.model = model or settings.openai_llm_model
        self.temperature = temperature
        self._semaphore = asyncio.Semaphore(concurrency)
        self._client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    async def _call_judge(self, prompt: str) -> Dict[str, Any]:
        """
        Call the OpenAI judge and parse the JSON response.

        Returns a dict with at least ``score`` (int 1-5) and ``reason`` (str).
        On parse/API failure, returns ``{"score": None, "reason": "<error>"}``.
        """
        async with self._semaphore:
            try:
                response = await self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.temperature,
                    max_tokens=120,
                    response_format={"type": "json_object"},
                )
                raw = response.choices[0].message.content or "{}"
                parsed = json.loads(raw)
                score = parsed.get("score")
                if not isinstance(score, int) or score < 1 or score > 5:
                    raise ValueError(f"Score out of expected range: {score!r}")
                return {
                    "score": int(score),
                    "reason": str(parsed.get("reason", "")),
                }
            except Exception as exc:
                logger.warning("RAG Triad judge call failed: %s", exc)
                return {"score": None, "reason": str(exc)}

    async def score_trace(
        self,
        trace: "QueryTrace",
        context_snippets: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Score a single ``QueryTrace`` on all three RAG Triad dimensions.

        Args:
            trace: A finalised ``QueryTrace`` with ``generated_content`` populated.
            context_snippets: Optional list of retrieved chunk texts to use as
                context. When omitted the scorer uses
                ``trace.retrieved_chunk_ids`` as placeholder labels
                (less informative but valid for ID-only runs).

        Returns:
            Dict with keys:
            - ``context_relevance`` (int | None): CR score 1-5, or None if skipped.
            - ``context_relevance_reason`` (str | None)
            - ``groundedness`` (int | None): G score 1-5, or None if skipped.
            - ``groundedness_reason`` (str | None)
            - ``answer_relevance`` (int | None): AR score 1-5.
            - ``answer_relevance_reason`` (str | None)
            - ``variant_name`` (str)
            - ``query_id`` (str)
        """
        query_text = trace.query_text or ""
        answer = _truncate(trace.generated_content or "", _MAX_ANSWER_CHARS)
        is_llm_only = trace.variant_name == "llm_only"

        # Build context string from snippets or ID list
        if context_snippets:
            context_text = _truncate(
                "\n---\n".join(context_snippets), _MAX_CONTEXT_CHARS
            )
        else:
            ids = trace.retrieved_chunk_ids or []
            context_text = "\n".join(f"• {cid}" for cid in ids[:10]) or "(no context)"

        result: Dict[str, Any] = {
            "query_id": trace.query_id,
            "variant_name": trace.variant_name,
            "context_relevance": None,
            "context_relevance_reason": None,
            "groundedness": None,
            "groundedness_reason": None,
            "answer_relevance": None,
            "answer_relevance_reason": None,
        }

        # CR and G are skipped for llm_only (no retrieval)
        if not is_llm_only:
            cr_prompt = _CR_PROMPT.format(query=query_text, context=context_text)
            g_prompt = _G_PROMPT.format(
                query=query_text, context=context_text, answer=answer
            )
            cr_result, g_result = await asyncio.gather(
                self._call_judge(cr_prompt),
                self._call_judge(g_prompt),
            )
            result["context_relevance"] = cr_result["score"]
            result["context_relevance_reason"] = cr_result["reason"]
            result["groundedness"] = g_result["score"]
            result["groundedness_reason"] = g_result["reason"]

        # AR is scored for all variants
        ar_prompt = _AR_PROMPT.format(query=query_text, answer=answer)
        ar_result = await self._call_judge(ar_prompt)
        result["answer_relevance"] = ar_result["score"]
        result["answer_relevance_reason"] = ar_result["reason"]

        return result

    async def score_batch(
        self,
        traces: List["QueryTrace"],
        context_map: Optional[Dict[str, List[str]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Score a batch of traces concurrently (respecting ``concurrency`` limit).

        Args:
            traces: List of ``QueryTrace`` objects to score.
            context_map: Optional dict mapping ``query_id`` → list of chunk text
                snippets.  When omitted, ID-only context is used.

        Returns:
            List of score dicts in the same order as *traces*.
        """
        context_map = context_map or {}
        tasks = [
            self.score_trace(
                trace,
                context_snippets=context_map.get(trace.query_id),
            )
            for trace in traces
        ]
        return await asyncio.gather(*tasks)


# ── CLI entry point ────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="RAG Triad LLM-as-judge scoring for benchmark results."
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        metavar="DIR",
        help="Directory containing *_results.json files from the benchmark runner.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        metavar="DIR",
        help="Output directory for rag_triad score files. "
             "Defaults to <input>/rag_triad/.",
    )
    parser.add_argument(
        "--variants",
        nargs="+",
        default=None,
        metavar="VARIANT",
        help="Variant names to score. Defaults to all found in --input.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        metavar="N",
        help="Max simultaneous OpenAI calls (default: 5).",
    )
    parser.add_argument(
        "--model",
        default=None,
        metavar="MODEL",
        help="OpenAI model for evaluation (default: settings.openai_llm_model).",
    )
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()

    input_dir = args.input
    output_dir = args.output or (input_dir / "rag_triad")
    output_dir.mkdir(parents=True, exist_ok=True)

    scorer = RAGTriadScorer(model=args.model, concurrency=args.concurrency)

    # Discover result files
    result_files = sorted(input_dir.glob("*_results.json"))
    if not result_files:
        print(f"No *_results.json files found in {input_dir}")
        return

    for result_file in result_files:
        variant_name = result_file.stem.replace("_results", "")
        if args.variants and variant_name not in args.variants:
            continue

        print(f"Scoring variant: {variant_name} …")
        with open(result_file, encoding="utf-8") as f:
            raw_traces = json.load(f)

        # Reconstruct lightweight trace-like objects for scoring
        class _TraceLike:
            pass

        traces_to_score: List[Any] = []
        for td in raw_traces:
            t = _TraceLike()
            for k, v in td.items():
                setattr(t, k, v)
            # Ensure required attributes exist with defaults
            if not hasattr(t, "retrieved_chunk_ids"):
                t.retrieved_chunk_ids = []
            if not hasattr(t, "generated_content"):
                t.generated_content = ""
            traces_to_score.append(t)

        scores = await scorer.score_batch(traces_to_score)

        out_file = output_dir / f"{variant_name}_rag_triad.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(scores, f, indent=2, ensure_ascii=False)

        scored = sum(1 for s in scores if s.get("answer_relevance") is not None)
        print(f"  ✓ Scored {scored}/{len(scores)} traces → {out_file.name}")


if __name__ == "__main__":
    asyncio.run(_main())

