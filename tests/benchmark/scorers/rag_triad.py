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
import re
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
_MAX_RETRIES = 6            # max retry attempts on RateLimitError


# ── Helpers ────────────────────────────────────────────────────────────────────

def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n…[truncated]"


def _parse_retry_after(error_msg: str) -> Optional[float]:
    """Extract the suggested retry delay in seconds from an OpenAI rate-limit message."""
    m = re.search(r"try again in (\d+(?:\.\d+)?)(ms|s)", error_msg, re.IGNORECASE)
    if m:
        val = float(m.group(1))
        return val / 1000.0 if m.group(2).lower() == "ms" else val
    return None


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
        concurrency: int = 1,
        temperature: float = 0.0,
        api_delay_s: float = 2.2,
    ) -> None:
        self.model = model or settings.openai_llm_model
        self.temperature = temperature
        self._api_delay_s = api_delay_s
        self._semaphore = asyncio.Semaphore(concurrency)
        self._client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    async def _call_judge(self, prompt: str) -> Dict[str, Any]:
        """
        Call the OpenAI judge and parse the JSON response.

        Retries up to ``_MAX_RETRIES`` times on ``RateLimitError``, waiting
        the duration suggested by the API (or exponential backoff if not
        parseable).  A per-call inter-request delay (``api_delay_s``) is
        applied inside the semaphore slot before every API call to prevent
        sustained TPM budget exhaustion.

        Returns a dict with at least ``score`` (int 1-5) and ``reason`` (str).
        On non-retryable failure, returns ``{"score": None, "reason": "<error>"``}.
        """
        async with self._semaphore:
            if self._api_delay_s > 0:
                await asyncio.sleep(self._api_delay_s)
            for attempt in range(_MAX_RETRIES):
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
                except openai.RateLimitError as exc:
                    wait = _parse_retry_after(str(exc)) or (2.0 ** (attempt + 1))
                    wait = min(wait + 1.0, 60.0)  # 1s safety buffer, cap at 60s
                    logger.warning(
                        "Rate limit hit (attempt %d/%d), retrying in %.1fs",
                        attempt + 1, _MAX_RETRIES, wait,
                    )
                    await asyncio.sleep(wait)
                except Exception as exc:
                    logger.warning("RAG Triad judge call failed: %s", exc)
                    return {"score": None, "reason": str(exc)}
            return {"score": None, "reason": f"Rate limit exceeded after {_MAX_RETRIES} retries"}

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
        # For multi-turn queries, turn4_response is generated against the full
        # conversation context culminating in turn3_query (the post-clarification
        # user message).  Evaluating AR and CR against the original vague
        # turn1_query would artificially deflate scores because the answer
        # correctly addresses the clarified question, not the vague opening.
        # Single-turn queries have no turn3_query, so turn1_query is always used.
        is_multiturn = getattr(trace, "is_multiturn", False)
        turn3 = getattr(trace, "turn3_query", None)
        if is_multiturn and turn3:
            query_text = turn3
        else:
            query_text = getattr(trace, "turn1_query", None) or ""

        answer = _truncate(trace.generated_response or "", _MAX_ANSWER_CHARS)
        is_llm_only = trace.variant_name == "llm_only"

        # Build context string from snippets or ID list
        if context_snippets:
            context_text = _truncate(
                "\n---\n".join(context_snippets), _MAX_CONTEXT_CHARS
            )
        else:
            per_k = getattr(trace, "retrieved_chunk_ids_per_k", {}) or {}
            if per_k:
                # Keys may be strings (JSON); sort numerically to get highest K
                best_k = max(per_k, key=lambda x: int(x))
                ids = per_k.get(best_k, [])
            else:
                ids = []
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
        "--query-ids",
        nargs="+",
        default=None,
        metavar="ID",
        help="Score only these query IDs (e.g. Q001 Q002). Use for probe/smoke runs.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        metavar="N",
        help="Randomly sample N queries per variant (probe run).",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        metavar="N",
        help="Max simultaneous OpenAI calls (default: 1). Keep at 1 for 30K TPM accounts.",
    )
    parser.add_argument(
        "--api-delay-ms",
        type=int,
        default=2200,
        metavar="MS",
        help="Delay between API calls in milliseconds (default: 2200). "
             "At 1000 tokens/call and 30K TPM limit, use >=2000ms.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip query IDs already present in the output file.",
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

    scorer = RAGTriadScorer(
        model=args.model,
        concurrency=args.concurrency,
        api_delay_s=args.api_delay_ms / 1000.0,
    )

    query_id_filter = set(args.query_ids) if args.query_ids else None

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
            data = json.load(f)

        # Runner writes {"variant": ..., "traces": [...]} — unwrap the traces list.
        if isinstance(data, dict) and "traces" in data:
            raw_traces = data["traces"]
        elif isinstance(data, list):
            raw_traces = data
        else:
            print(f"  ⚠ Unexpected JSON structure in {result_file.name}, skipping.")
            continue

        # Filter by explicit query IDs (probe / smoke runs)
        if query_id_filter:
            raw_traces = [td for td in raw_traces if td.get("query_id") in query_id_filter]
            if not raw_traces:
                print(f"  ⚠ No matching query IDs found for {variant_name}, skipping.")
                continue

        # Random sample (probe run without specifying IDs)
        if args.sample_size and len(raw_traces) > args.sample_size:
            import random
            raw_traces = random.sample(raw_traces, args.sample_size)
            print(f"  Sampled {args.sample_size}/{len(data['traces'] if isinstance(data, dict) else data)} traces.")

        # Resume: load existing scored results and skip already-done query IDs
        out_file = output_dir / f"{variant_name}_rag_triad.json"
        accumulated_scores: List[Dict[str, Any]] = []
        skip_ids: set = set()
        if args.resume and out_file.exists():
            try:
                with out_file.open(encoding="utf-8") as f:
                    existing = json.load(f)
                accumulated_scores = existing if isinstance(existing, list) else []
                skip_ids = {s["query_id"] for s in accumulated_scores if isinstance(s, dict) and "query_id" in s}
                raw_traces = [td for td in raw_traces if td.get("query_id") not in skip_ids]
                print(f"  Resume: {len(skip_ids)} already scored, {len(raw_traces)} remaining.")
            except (json.JSONDecodeError, OSError) as exc:
                print(f"  ⚠ Could not load existing scores ({exc}), starting fresh.")

        if not raw_traces:
            print(f"  ✓ All traces already scored for {variant_name}.")
            continue

        # Reconstruct lightweight trace-like objects for scoring
        class _TraceLike:
            pass

        traces_to_score: List[Any] = []
        context_map: Dict[str, List[str]] = {}
        for td in raw_traces:
            t = _TraceLike()
            for k, v in td.items():
                setattr(t, k, v)
            # Ensure required attributes exist with defaults
            if not hasattr(t, "retrieved_chunk_ids_per_k"):
                t.retrieved_chunk_ids_per_k = {}
            # Reverse alias: runner serializes generated_response as turn4_response
            # (multi-turn) or turn2_response (single-turn) in the JSON files.
            if not getattr(t, "generated_response", None):
                t.generated_response = (
                    getattr(t, "turn4_response", None)
                    or getattr(t, "turn2_response", None)
                    or ""
                )
            if not hasattr(t, "turn1_query"):
                # backwards-compat: raw JSON may use old key name
                t.turn1_query = getattr(t, "query_text", "")
            traces_to_score.append(t)
            # Build context_map from citation texts for richer CR / G scoring.
            citations = getattr(t, "generated_citations", None) or []
            snippets = [c.get("text", "") for c in citations if c.get("text")]
            if snippets:
                context_map[t.query_id] = snippets

        # Sort by query_id so output JSON is in Q001, Q002, … order.
        traces_to_score.sort(key=lambda t: t.query_id)

        total = len(traces_to_score)
        print(f"  Scoring {total} trace(s) with concurrency={args.concurrency}, "
              f"delay={args.api_delay_ms}ms …")

        # Score one trace at a time for incremental writes and progress visibility
        for idx, trace in enumerate(traces_to_score, start=1):
            score = await scorer.score_trace(
                trace,
                context_snippets=context_map.get(trace.query_id),
            )
            accumulated_scores.append(score)

            # Write incrementally after every trace so interrupted runs resume cleanly
            with out_file.open("w", encoding="utf-8") as f:
                json.dump(accumulated_scores, f, indent=2, ensure_ascii=False)

            cr = score.get("context_relevance")
            g  = score.get("groundedness")
            ar = score.get("answer_relevance")
            print(
                f"  [{idx}/{total}] {trace.query_id}: "
                f"CR={cr!s:>4}  G={g!s:>4}  AR={ar!s:>4}"
            )

        scored = sum(1 for s in accumulated_scores if s.get("answer_relevance") is not None)
        print(f"  ✓ Variant {variant_name}: {scored}/{len(accumulated_scores)} scored → {out_file.name}")


if __name__ == "__main__":
    asyncio.run(_main())

