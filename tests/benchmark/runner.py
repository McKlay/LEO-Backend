"""
Benchmark runner for the LEO pipeline evaluation framework.

Orchestrates query execution across all pipeline variants in three modes:
  - analysis_only   Stage 1 only — fast, GPT-4o-mini, used for
                    --validate clarification pre-flight diagnostics only
  - retrieval_only  Stage 1 + 2 — embeddings only, used for Tables 2–4
  - full            All stages + LLM generation, used for Tables 6–10

Entry point:
    python -m tests.benchmark.runner --help

Example commands:
    python -m tests.benchmark.runner --smoke
    python -m tests.benchmark.runner --validate all
    python -m tests.benchmark.runner --mode retrieval_only --top-k 3 5 10 \\
        --variant full_pipeline dense_only lexical_only symbolic_only
    python -m tests.benchmark.runner --mode full \\
        --variant llm_only stage2_only full_pipeline
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.config import settings
from core.logging import get_logger, setup_logging
from tests.benchmark.config import (
    VARIANTS_BY_NAME,
    VariantConfig,
    apply_variant,
    get_queries_for_variant,
    get_variant_by_name,
    reset_singletons,
)
from tests.benchmark.collector import QueryTrace, ResultCollector
from tests.benchmark.scorers.retrieval import score_retrieval
from tests.benchmark.scorers.answer_quality import score_answer
from tests.benchmark.scorers.citation import score_citations

logger = get_logger(__name__)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_effective_query(query: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Determine the effective user message and prior turns for a query.

    For single-turn queries: effective message = query['query_text'], no prior turns.
    For multi-turn queries: effective message = last user turn in conversation_history;
        prior turns = all entries before that final user turn.

    The benchmark JSON uses 'text' as the message key in conversation_history entries.

    Args:
        query: A benchmark query dict

    Returns:
        Tuple of (effective_query_text, prior_turns)
    """
    if query.get("query_type") != "multi_turn":
        return query["query_text"], []

    history = query.get("conversation_history", [])
    if not history:
        return query["query_text"], []

    # Scan backwards for the last user turn
    for i in range(len(history) - 1, -1, -1):
        if history[i].get("role") == "user":
            # Support both 'text' and 'content' keys in history entries
            text = history[i].get("text") or history[i].get("content", "")
            prior_turns = history[:i]
            return text, prior_turns

    # Fallback: no user turn found in history
    return query["query_text"], []


# ── Main Runner ────────────────────────────────────────────────────────────────

class BenchmarkRunner:
    """
    Orchestrates benchmark evaluation across pipeline variants.

    Supports three execution modes:
      - analysis_only  Stage 1 only (query analysis)
      - retrieval_only Stage 1 + Stage 2 (retrieval, no generation)
      - full           All stages including LLM generation

    All pipeline calls are made in-process via app.containers — no uvicorn
    server is required.
    """

    def __init__(
        self,
        queries_path: Path,
        output_dir: Path,
        mode: str = "full",
        top_k_values: Optional[List[int]] = None,
        query_ids: Optional[List[str]] = None,
        api_delay_ms: int = 200,
        resume: bool = False,
    ):
        """
        Args:
            queries_path:  Path to benchmark-queries.json
            output_dir:    Directory for results
            mode:          Execution mode (analysis_only | retrieval_only | full)
            top_k_values:  K values for retrieval_only mode
            query_ids:     Restrict run to specific query IDs (e.g. ["Q007"])
            api_delay_ms:  Delay between API calls in milliseconds
            resume:        Skip already-completed query–variant pairs
        """
        self.queries_path = queries_path
        self.output_dir = output_dir
        self.mode = mode
        self.top_k_values = sorted(top_k_values or [5])
        self.query_ids = set(query_ids) if query_ids else None
        self.api_delay_ms = api_delay_ms
        self.resume = resume

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.collector = ResultCollector(output_dir)
        self.all_queries = self._load_queries()

        logger.info(
            f"BenchmarkRunner initialized: mode={mode}, "
            f"queries={len(self.all_queries)}, top_k={self.top_k_values}, "
            f"resume={resume}"
        )

    # ── Query loading ──────────────────────────────────────────────────────────

    def _load_queries(self) -> List[Dict[str, Any]]:
        """Load and optionally filter benchmark queries from JSON."""
        data = json.loads(self.queries_path.read_text(encoding="utf-8"))
        queries = data.get("queries", [])
        if self.query_ids:
            queries = [q for q in queries if q["query_id"] in self.query_ids]
            logger.info(f"Filtered to {len(queries)} queries via --query-ids")
        return queries

    # ── Multi-turn history injection ───────────────────────────────────────────

    async def _inject_conversation_history(
        self,
        conversation_id: str,
        prior_turns: List[Dict[str, Any]],
    ) -> None:
        """
        Write prior conversation turns into the conversation memory store.

        This creates the realistic context Stage 1 needs for multi-turn
        query summarization and pronoun resolution.

        Args:
            conversation_id: Fresh UUID used as the memory key
            prior_turns: Ordered list of {role, text|content} entries to inject
        """
        from app.containers import get_conversation_pipeline

        conversation = get_conversation_pipeline()
        for turn in prior_turns:
            role = turn.get("role", "user")
            content = turn.get("text") or turn.get("content", "")
            if role == "user":
                await conversation.add_user_message(
                    session_id=conversation_id, content=content
                )
            elif role == "assistant":
                await conversation.add_assistant_message(
                    session_id=conversation_id, content=content
                )

    # ── Execution modes ────────────────────────────────────────────────────────

    async def _run_analysis_only(
        self,
        query_text: str,
        language: str,
        conversation_id: str,
        has_prior_turns: bool,
    ) -> None:
        """
        Call Stage 1 (query analysis) directly and record the result.

        Args:
            query_text:     Effective user message
            language:       Detected/declared language code
            conversation_id: Conversation ID for history lookup
            has_prior_turns: Whether prior turns were injected into memory
        """
        from app.containers import get_conversation_pipeline, get_query_analysis_pipeline

        analysis_pipeline = get_query_analysis_pipeline()

        # Retrieve injected conversation context for the analysis call
        context: List[Dict[str, str]] = []
        if has_prior_turns:
            conversation = get_conversation_pipeline()
            context = await conversation.get_conversation_context(
                session_id=conversation_id,
                include_last_n=settings.max_conversation_history,
            )

        t0 = time.monotonic()
        analysis = await analysis_pipeline.analyze(
            query=query_text,
            conversation_history=context or None,
            preferred_language=language,
        )
        elapsed = time.monotonic() - t0

        self.collector.record_analysis(analysis, analysis_time_s=elapsed)

    async def _run_retrieval_only(
        self,
        query_text: str,
        language: str,
        conversation_id: str,
        has_prior_turns: bool,
    ) -> None:
        """
        Call Stage 1 + Stage 2 directly and record both results.

        Retrieval is performed at max(top_k_values). The full ranked list is
        stored in the trace; scorers slice it to compute metrics at smaller K.

        Args:
            query_text:     Effective user message
            language:       Detected/declared language code
            conversation_id: Conversation ID for history lookup
            has_prior_turns: Whether prior turns were injected into memory
        """
        from app.containers import (
            get_conversation_pipeline,
            get_query_analysis_pipeline,
            get_retrieval_pipeline,
        )

        max_k = max(self.top_k_values)
        analysis = None

        # Stage 1: query analysis (skipped when enable_query_analysis=False)
        if settings.enable_query_analysis:
            context: List[Dict[str, str]] = []
            if has_prior_turns:
                conversation = get_conversation_pipeline()
                context = await conversation.get_conversation_context(
                    session_id=conversation_id,
                    include_last_n=settings.max_conversation_history,
                )

            t0 = time.monotonic()
            analysis = await get_query_analysis_pipeline().analyze(
                query=query_text,
                conversation_history=context or None,
                preferred_language=language,
            )
            self.collector.record_analysis(analysis, analysis_time_s=time.monotonic() - t0)

        # Stage 2: separate retrieval call per K value.
        # RRF merges scores across sources at retrieval time; sub-selecting top-K
        # from a larger pool does NOT reproduce native top-K rankings. Each K
        # therefore needs its own independent retrieval call (Decision 8).
        retrieval_pipeline = get_retrieval_pipeline()
        original_lang = analysis.original_language if analysis else language
        translation_active = settings.enable_translation or original_lang in ("en", "mixed", "")
        retrieval_query = (
            analysis.normalized_query_en
            if (analysis and analysis.normalized_query_en and translation_active)
            else query_text
        )

        results_by_k: Dict[int, Any] = {}
        total_retrieval_time = 0.0
        for k in self.top_k_values:
            t0 = time.monotonic()
            results_by_k[k] = await retrieval_pipeline.retrieve(
                query=retrieval_query,
                keywords=analysis.keywords if analysis else None,
                articles=analysis.articles if analysis else None,
                top_k=k,
            )
            total_retrieval_time += time.monotonic() - t0
        self.collector.record_retrieval_per_k(
            results_by_k, retrieval_time_s=total_retrieval_time
        )

    async def _run_full(self, query_text: str, language: str, conversation_id: str) -> str:
        """
        Stream all pipeline stages via process_message_stream and collect events.

        Args:
            query_text:     Effective user message
            language:       Detected/declared language code
            conversation_id: Conversation ID (prior turns already injected)

        Returns:
            The LangChain session_id created for this call, so that Phase 2
            (_run_phase2) can reuse it to preserve Turn 4 exchange context.
        """
        from app.containers import get_chat_orchestrator

        orchestrator = get_chat_orchestrator()
        session_id = f"benchmark-{uuid.uuid4().hex[:8]}"

        async for event in orchestrator.process_message_stream(
            session_id=session_id,
            conversation_id=conversation_id,
            user_message=query_text,
            language=language,
        ):
            self.collector.process_event(event)

        return session_id

    async def _run_phase2(
        self,
        turn5_query: str,
        language: str,
        session_id: str,
        conversation_id: str,
    ) -> None:
        """
        Run Phase 2 (Turn 5 → Turn 6) for multi-turn queries in full mode.

        Sends turn5_query through process_message_stream reusing the same
        session_id and conversation_id from Phase 1, so LangChain memory
        (session_id) already holds the Turn 4 exchange and the conversation
        store (conversation_id) holds Turns 1–3 from history injection.

        All three Table 8 configs (llm_only, stage2_only, full_pipeline)
        receive full conversation history (Turns 1–5) before generating Turn 6.
        They are distinguished only by their retrieval query, not by whether
        history is provided (Decision 4).

        Phase 2 is skipped in retrieval_only mode — Table 8 reports
        answer-quality metrics only; no Phase 2 retrieval pass is needed
        for Turn 6 (Decision 2).

        Args:
            turn5_query:     Turn 5 user message from benchmark-queries.json
            language:        Language code for the query
            session_id:      LangChain session ID reused from Phase 1
            conversation_id: Conversation ID holding Turns 1–3 from injection
        """
        from app.containers import get_chat_orchestrator

        orchestrator = get_chat_orchestrator()

        async for event in orchestrator.process_message_stream(
            session_id=session_id,
            conversation_id=conversation_id,
            user_message=turn5_query,
            language=language,
        ):
            self.collector.process_event_phase2(event)

    # ── Single query orchestration ─────────────────────────────────────────────

    async def _run_one_query(
        self,
        query: Dict[str, Any],
        variant: VariantConfig,
    ) -> QueryTrace:
        """
        Run a single query through the configured pipeline mode.

        Handles multi-turn history injection, mode dispatch, and trace
        finalization with disk persistence.

        Args:
            query:   Benchmark query dict
            variant: Active variant configuration

        Returns:
            Finalized QueryTrace
        """
        conversation_id = str(uuid.uuid4())
        effective_query, prior_turns = _get_effective_query(query)

        trace = self.collector.start_trace(
            query,
            variant.name,
            turn3_query=effective_query,
            prior_turn_count=len(prior_turns),
        )

        try:
            # Inject prior turns into memory for multi-turn queries
            if prior_turns:
                logger.debug(
                    f"Injecting {len(prior_turns)} prior turns for "
                    f"{query['query_id']} ({query.get('query_type')})"
                )
                await self._inject_conversation_history(conversation_id, prior_turns)

            language = query.get("language", "en")
            has_prior = bool(prior_turns)

            if self.mode == "analysis_only":
                await self._run_analysis_only(
                    effective_query, language, conversation_id, has_prior
                )
            elif self.mode == "retrieval_only":
                await self._run_retrieval_only(
                    effective_query, language, conversation_id, has_prior
                )
            elif self.mode == "full":
                session_id = await self._run_full(
                    effective_query, language, conversation_id
                )
                # Phase 2: run Turn 5 → Turn 6 for multi-turn queries that have
                # turn5_query populated. Skipped in retrieval_only mode (Decision 2).
                if (
                    query.get("query_type") == "multi_turn"
                    and query.get("turn5_query")
                ):
                    await self._run_phase2(
                        turn5_query=query["turn5_query"],
                        language=language,
                        session_id=session_id,
                        conversation_id=conversation_id,
                    )
            else:
                raise ValueError(f"Unknown execution mode: {self.mode!r}")

        except Exception as exc:
            logger.error(
                f"Error running {query['query_id']}/{variant.name}: {exc}",
                exc_info=True,
            )
            if self.collector.current_trace is not None:
                self.collector.current_trace.error = str(exc)

        # Apply automated scorers before persisting — scores are included in
        # both partial JSON and the consolidated variant results file.
        self._apply_scores(self.collector.current_trace)

        return self.collector.finalize_trace(persist=True)

    def _apply_scores(self, trace: Optional[QueryTrace]) -> None:
        """
        Compute and store automated metric scores on the active trace.

        - retrieval_only / full with retrieval data: Recall@K, Hit Rate@K, MRR
        - full: Token F1, ROUGE-L, Exact Match, Citation P/R
        """
        if trace is None or trace.error:
            return

        scores: Dict[str, Any] = {}

        # Retrieval metrics — whenever per-K results are present
        if trace.retrieved_chunk_ids_per_k:
            k_values = sorted(trace.retrieved_chunk_ids_per_k.keys())
            scores.update(score_retrieval(trace, k_values=k_values))

        # Answer-quality + citation metrics — whenever a generated response exists
        if trace.generated_response:
            aq = score_answer(trace)
            if aq:
                scores.update(aq)
            cit = score_citations(trace)
            if cit:
                scores.update(cit)

        trace.scores = scores

        if scores:
            score_summary = "  ".join(
                f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}"
                for k, v in sorted(scores.items())
            )
            logger.info(f"  SCORES | {score_summary}")

    # ── Main execution loop ────────────────────────────────────────────────────

    async def run(self, variants: List[VariantConfig]) -> Dict[str, List[QueryTrace]]:
        """
        Execute the benchmark loop over all specified variants and queries.

        For each variant: applies settings → resets singletons → runs all
        filtered queries in sequence → writes consolidated results.

        Args:
            variants: Ordered list of VariantConfig objects to evaluate

        Returns:
            Dict mapping variant_name → list of QueryTrace results
        """
        manifest_path = self.output_dir / "run_manifest.json"
        new_variant_names = [v.name for v in variants]

        if self.resume and manifest_path.exists():
            # Merge with existing manifest — preserve cumulative history across sessions
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
            existing_variants = existing.get("variants", [])
            merged_variants = existing_variants + [
                n for n in new_variant_names if n not in existing_variants
            ]
            merged_k = sorted(set(existing.get("top_k_values", [])) | set(self.top_k_values))
            manifest: Dict[str, Any] = {
                "started_at": existing.get("started_at", datetime.utcnow().isoformat()),
                "mode": self.mode,
                "top_k_values": merged_k,
                "variants": merged_variants,
                "total_queries_in_set": max(
                    existing.get("total_queries_in_set", 0), len(self.all_queries)
                ),
                "results_summary": existing.get("results_summary", {}),
                "resumed_at": datetime.utcnow().isoformat(),
            }
        else:
            if manifest_path.exists():
                logger.warning(
                    "Existing run_manifest.json found in output_dir but --resume was "
                    "not set — previous manifest will be overwritten. "
                    "Pass --resume to continue a prior run."
                )
            manifest = {
                "started_at": datetime.utcnow().isoformat(),
                "mode": self.mode,
                "top_k_values": self.top_k_values,
                "variants": new_variant_names,
                "total_queries_in_set": len(self.all_queries),
            }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        all_results: Dict[str, List[QueryTrace]] = {}

        for variant in variants:
            logger.info("=" * 60)
            logger.info(f"Variant: {variant.display_name}")
            logger.info("=" * 60)

            apply_variant(variant)
            reset_singletons()

            if self.resume:
                self.collector.load_partial_results(variant.name)

            queries = get_queries_for_variant(variant, self.all_queries)
            logger.info(f"Running {len(queries)} queries for '{variant.name}'")

            for i, query in enumerate(queries, 1):
                qid = query["query_id"]

                if self.resume and self.collector.is_completed(qid, variant.name):
                    logger.info(f"[{i}/{len(queries)}] Skip {qid} (already completed)")
                    continue

                logger.info(
                    f"[{i}/{len(queries)}] {qid} | "
                    f"lang={query.get('language', '?')} | "
                    f"{'ambiguous' if query.get('is_ambiguous') else 'clear'} | "
                    f"{query.get('query_type', 'single_turn')}"
                )

                trace = await self._run_one_query(query, variant)

                if trace.error:
                    logger.warning(f"  ERROR: {trace.error}")
                else:
                    logger.info(
                        f"  OK | clarify={trace.is_clarification_response} | "
                        f"chunks={trace.retrieval_count or 0} | "
                        f"content_len={len(trace.generated_response or '')}"
                    )

                if self.api_delay_ms > 0:
                    await asyncio.sleep(self.api_delay_ms / 1000)

            all_results[variant.name] = self.collector.finalize_variant(variant.name)

        # Write completed manifest — merge results_summary with any prior sessions
        manifest["completed_at"] = datetime.utcnow().isoformat()
        existing_summary = manifest.get("results_summary", {})
        new_summary = {name: len(traces) for name, traces in all_results.items()}
        manifest["results_summary"] = {**existing_summary, **new_summary}
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        return all_results

    # ── Pre-flight validation: smoke test ──────────────────────────────────────

    async def run_smoke_test(self) -> None:
        """
        Run queries through the full pipeline as a sanity check.

        When --query-ids is specified, runs only those queries (targeted
        debugging with minimal token usage).  Otherwise selects 4
        representative queries: 1 EN single-turn clear, 1 Filipino,
        1 Cebuano, 1 multi-turn (ambiguous).

        Prints a diagnostic summary; does not call finalize_variant().
        """
        print("\n" + "═" * 60)
        print("SMOKE TEST")
        print("═" * 60)

        apply_variant(get_variant_by_name("full_pipeline"))
        reset_singletons()

        if self.query_ids:
            # Targeted mode: run only the user-specified queries
            smoke_queries = [
                (f"{q.get('query_type', '?')}_{q.get('language', '?')}", q)
                for q in self.all_queries
            ]
            print(f"\nTargeted mode: {len(smoke_queries)} query(ies) via --query-ids")
        else:
            smoke_queries = self._select_smoke_queries()
            if len(smoke_queries) < 4:
                print(f"WARNING: Found only {len(smoke_queries)}/4 representative queries")

        saved_mode = self.mode
        self.mode = "full"
        results: List[Tuple[str, QueryTrace]] = []

        for label, query in smoke_queries:
            print(f"\n[{label}] {query['query_id']}: {query['query_text'][:70]}...")
            trace = await self._run_one_query(query, get_variant_by_name("full_pipeline"))
            results.append((label, trace))

            if trace.error:
                print(f"  Status: FAIL — {trace.error}")
            else:
                parts = []
                if trace.needs_clarification is not None:
                    parts.append(f"clarification={trace.needs_clarification}")
                if trace.retrieval_count is not None:
                    parts.append(f"chunks={trace.retrieval_count}")
                if trace.generated_response:
                    parts.append(f"content_len={len(trace.generated_response)}")
                print(f"  Status: OK — {' | '.join(parts)}")

            if self.api_delay_ms > 0:
                await asyncio.sleep(self.api_delay_ms / 1000)

        self.mode = saved_mode

        passed = sum(1 for _, t in results if not t.error)
        print(f"\n{'─' * 60}")
        print(f"SMOKE TEST: {passed}/{len(results)} passed")
        print("═" * 60 + "\n")

    def _select_smoke_queries(self) -> List[Tuple[str, Dict[str, Any]]]:
        """Select one query for each of the 4 smoke test criteria.

        All ambiguous queries are now multi-turn, so those categories are
        merged into a single 'multi_turn_ambiguous' criterion.
        """
        criteria: List[Tuple[str, Any]] = [
            ("EN_clear", lambda q: (
                q["language"] == "en"
                and not q.get("is_ambiguous")
                and q.get("query_type") == "single_turn"
            )),
            ("FIL", lambda q: (
                q["language"] == "fil"
                and q.get("query_type") == "single_turn"
            )),
            ("CEB", lambda q: (
                q["language"] == "ceb"
                and q.get("query_type") == "single_turn"
            )),
            ("multi_turn_ambiguous", lambda q: (
                q.get("query_type") == "multi_turn"
                and q.get("is_ambiguous")
            )),
        ]
        selected: List[Tuple[str, Dict]] = []
        used_ids: set = set()

        for label, predicate in criteria:
            for q in self.all_queries:
                if q["query_id"] not in used_ids and predicate(q):
                    selected.append((label, q))
                    used_ids.add(q["query_id"])
                    break

        return selected

    # ── Pre-flight validation: clarification ───────────────────────────────────

    async def run_validate_clarification(
        self, sample_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Validate clarification detection accuracy before committing to a full run.

        For ambiguous queries (all multi-turn), sends the *original vague Turn 1*
        query directly with NO conversation history. This tests whether Stage 1
        correctly identifies the need for clarification.

        For clear queries, sends the query as-is through normal analysis.

        Args:
            sample_size: Limit each category (ambiguous/clear) to N queries.
                         None = use all available.

        Returns:
            Dict with precision, recall, f1, counts, and failure list
        """
        from app.containers import get_query_analysis_pipeline

        print("\n" + "═" * 60)
        print("CLARIFICATION VALIDATION")
        print("═" * 60)

        apply_variant(get_variant_by_name("full_pipeline"))
        reset_singletons()

        ambiguous = [q for q in self.all_queries if q.get("is_ambiguous")]
        clear = [q for q in self.all_queries if not q.get("is_ambiguous")]
        if sample_size is not None:
            ambiguous = ambiguous[:sample_size]
            clear = clear[:sample_size]
        else:
            ambiguous = ambiguous[:30]
            clear = clear[:20]
        test_set = ambiguous + clear

        print(
            f"\nRunning {len(ambiguous)} ambiguous + {len(clear)} clear queries "
            f"through analysis_only..."
        )

        tp = fp = fn = tn = 0
        failures: List[Dict[str, Any]] = []
        analysis_pipeline = get_query_analysis_pipeline()

        for query in test_set:
            is_ambiguous = query.get("is_ambiguous", False)

            # For ambiguous queries: send Turn 1 (the vague original query)
            # directly WITHOUT history. This tests clarification detection.
            # For clear queries: send query_text as-is.
            query_text = query["query_text"]
            language = query.get("language", "en")

            try:
                t0 = time.monotonic()
                analysis = await analysis_pipeline.analyze(
                    query=query_text,
                    conversation_history=None,
                    preferred_language=language,
                )
                elapsed = time.monotonic() - t0
                predicted = analysis.needs_clarification or False
            except Exception as exc:
                logger.error(
                    f"Error analyzing {query['query_id']}: {exc}", exc_info=True
                )
                predicted = False

            print(
                f"  {query['query_id']} ({language}) | "
                f"ambiguous={is_ambiguous} | predicted_clarify={predicted}"
            )

            if is_ambiguous and predicted:
                tp += 1
            elif not is_ambiguous and predicted:
                fp += 1
                failures.append({
                    "query_id": query["query_id"],
                    "type": "FP",
                    "text": query_text[:80],
                })
            elif is_ambiguous and not predicted:
                fn += 1
                failures.append({
                    "query_id": query["query_id"],
                    "type": "FN",
                    "text": query_text[:80],
                })
            else:
                tn += 1

            if self.api_delay_ms > 0:
                await asyncio.sleep(self.api_delay_ms / 1000)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0 else 0.0
        )

        print(f"\n  Ambiguous queries (n={len(ambiguous)}):")
        print(f"    TP (correctly flagged):       {tp}")
        print(f"    FN (missed clarification):    {fn}")
        print(f"  Clear queries (n={len(clear)}):")
        print(f"    TN (correctly not flagged):   {tn}")
        print(f"    FP (false clarification):     {fp}")
        print(f"\n  Precision: {precision:.3f}  |  Recall: {recall:.3f}  |  F1: {f1:.3f}")

        if failures:
            print(f"\n  Failures ({len(failures)}):")
            for entry in failures[:10]:
                print(f"    [{entry['type']}] {entry['query_id']}: {entry['text']}")

        print("═" * 60 + "\n")
        return {
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": precision, "recall": recall, "f1": f1,
            "failures": failures,
        }

    # ── Pre-flight validation: multi-turn ─────────────────────────────────────

    async def run_validate_multiturn(
        self, sample_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Validate multi-turn conversation handling before a full run.

        Runs multi-turn queries through analysis_only with history
        injection. Verifies:
          - Conversation history was injected (prior_turn_count > 0)
          - Stage 1 produced a consolidated normalized_query_en
          - Clarification was not re-triggered on the final turn
            (checks needs_clarification from Stage 1 analysis)
          - is_meta_conversational was not incorrectly flagged

        Args:
            sample_size: Limit to N multi-turn queries. None = use all.

        Returns:
            Dict with passed/failed counts and per-query diagnostics
        """
        print("\n" + "═" * 60)
        print("MULTI-TURN VALIDATION")
        print("═" * 60)

        apply_variant(get_variant_by_name("full_pipeline"))
        reset_singletons()

        multiturn = [q for q in self.all_queries if q.get("query_type") == "multi_turn"]
        if sample_size is not None:
            multiturn = multiturn[:sample_size]
        total = len(multiturn)
        print(f"\nRunning {total} multi-turn queries through analysis_only...")

        passed = failed = 0
        diagnostics: List[Dict[str, Any]] = []
        saved_mode = self.mode
        self.mode = "analysis_only"
        full_pipeline_variant = get_variant_by_name("full_pipeline")

        for query in multiturn:
            trace = await self._run_one_query(query, full_pipeline_variant)

            history_injected = trace.prior_turn_count > 0
            has_normalized = bool(trace.normalized_query_en)
            # Use needs_clarification (Stage 1 output) — is_clarification_response
            # is only populated in full mode via the 'complete' SSE event.
            no_reclarify = not (trace.needs_clarification or False)
            no_false_meta = not trace.is_meta_conversational

            ok = history_injected and has_normalized and no_reclarify and no_false_meta

            diag: Dict[str, Any] = {
                "query_id": query["query_id"],
                "language": query.get("language"),
                "history_injected": history_injected,
                "has_normalized_query": has_normalized,
                "no_reclarification": no_reclarify,
                "no_false_meta": no_false_meta,
                "ok": ok,
                "error": trace.error,
            }
            diagnostics.append(diag)

            status = "PASS" if ok else "FAIL"
            print(
                f"  {status} | {query['query_id']} ({query.get('language', '?')}) | "
                f"history={history_injected} | normalized={has_normalized} | "
                f"no_reclarify={no_reclarify} | no_meta={no_false_meta}"
            )

            if ok:
                passed += 1
            else:
                failed += 1

            if self.api_delay_ms > 0:
                await asyncio.sleep(self.api_delay_ms / 1000)

        self.mode = saved_mode

        status_line = (
            f"PASS (all {total} passed)"
            if passed >= total
            else f"FAIL ({passed}/{total} — investigate failures before proceeding)"
        )
        print(f"\n  Result: {passed}/{total} passed — {status_line}")
        if passed < total:
            print("  Failures require investigation before running the full benchmark.")

        print("═" * 60 + "\n")
        return {"passed": passed, "failed": failed, "diagnostics": diagnostics}


# ── CLI ────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        prog="python -m tests.benchmark.runner",
        description="LEO pipeline benchmark evaluation runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Pre-flight checks (cheap: GPT-4o-mini only)
  python -m tests.benchmark.runner --smoke
  python -m tests.benchmark.runner --validate all

  # Retrieval metrics at multiple K values (Tables 2-4)
  python -m tests.benchmark.runner --mode retrieval_only --top-k 3 5 10 \\
    --variant full_pipeline dense_only lexical_only symbolic_only

  # Full pipeline for answer quality (Tables 6-10)
  python -m tests.benchmark.runner --mode full \\
    --variant llm_only stage2_only full_pipeline

  # Debug a specific query
  python -m tests.benchmark.runner --mode full --variant full_pipeline \\
    --query-ids Q007 --log-level DEBUG --log-file debug_Q007.log

  # Resume an interrupted run
  python -m tests.benchmark.runner --mode full --variant full_pipeline \\
    --resume --output-dir results/run_001
""",
    )

    # Core execution
    parser.add_argument(
        "--mode",
        choices=["analysis_only", "retrieval_only", "full"],
        default="full",
        help="Execution mode (default: full)",
    )
    parser.add_argument(
        "--variant",
        nargs="+",
        metavar="VARIANT",
        help=(
            "One or more variant names to run. "
            "Available: " + ", ".join(VARIANTS_BY_NAME.keys())
        ),
    )
    parser.add_argument(
        "--top-k",
        nargs="+",
        type=int,
        default=[5],
        metavar="K",
        dest="top_k",
        help="K values for retrieval_only mode (default: 5)",
    )
    parser.add_argument(
        "--query-ids",
        nargs="+",
        metavar="QID",
        help="Run only specific query IDs (e.g. Q007 Q015)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        metavar="DIR",
        help="Output directory (default: tests/benchmark/results/run_<timestamp>)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip completed query–variant pairs from a previous run",
    )

    # Validation & debugging
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run 4 representative queries as a full-pipeline smoke test",
    )
    parser.add_argument(
        "--validate",
        choices=["clarification", "multiturn", "all"],
        metavar="MODE",
        help="Run pre-flight validation: clarification | multiturn | all",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO)",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        metavar="PATH",
        help="Write logs to this file path",
    )
    parser.add_argument(
        "--log-per-variant",
        action="store_true",
        help="Split logs into per-variant files inside output-dir",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress console output (log to file only)",
    )
    parser.add_argument(
        "--api-delay-ms",
        type=int,
        default=200,
        dest="api_delay_ms",
        help="Delay between OpenAI API calls in milliseconds (default: 200)",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        dest="sample_size",
        metavar="N",
        help=(
            "Limit each validation category to N queries "
            "(e.g. --sample-size 1 for minimal logic validation)"
        ),
    )

    return parser.parse_args()


def _configure_logging(args: argparse.Namespace) -> None:
    """Configure logging from parsed CLI args."""
    setup_logging(level=args.log_level, json_output=False)

    if args.log_file:
        file_handler = logging.FileHandler(args.log_file, encoding="utf-8")
        file_handler.setLevel(getattr(logging, args.log_level, logging.INFO))
        logging.getLogger().addHandler(file_handler)

    if args.quiet:
        root = logging.getLogger()
        for h in list(root.handlers):
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
                root.removeHandler(h)


async def _main() -> None:
    """Async CLI entry point."""
    args = _parse_args()
    _configure_logging(args)

    # Resolve output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(__file__).parent / "results" / f"run_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Locate benchmark queries
    queries_path = Path(__file__).parent / "data" / "benchmark-queries.json"
    if not queries_path.exists():
        print(f"ERROR: benchmark-queries.json not found at {queries_path}")
        raise SystemExit(1)

    runner = BenchmarkRunner(
        queries_path=queries_path,
        output_dir=output_dir,
        mode=args.mode,
        top_k_values=args.top_k,
        query_ids=args.query_ids,
        api_delay_ms=args.api_delay_ms,
        resume=args.resume,
    )

    # Smoke test
    if args.smoke:
        await runner.run_smoke_test()
        return

    # Pre-flight validation
    if args.validate:
        if args.validate in ("clarification", "all"):
            await runner.run_validate_clarification(sample_size=args.sample_size)
        if args.validate in ("multiturn", "all"):
            await runner.run_validate_multiturn(sample_size=args.sample_size)
        return

    # Full benchmark run — requires --variant
    if not args.variant:
        print("ERROR: --variant is required for benchmark runs")
        print(f"Available: {', '.join(VARIANTS_BY_NAME.keys())}")
        raise SystemExit(1)

    selected_variants: List[VariantConfig] = []
    for name in args.variant:
        try:
            selected_variants.append(get_variant_by_name(name))
        except ValueError as exc:
            print(f"ERROR: {exc}")
            raise SystemExit(1)

    await runner.run(selected_variants)
    print(f"\nResults written to: {output_dir}")


if __name__ == "__main__":
    asyncio.run(_main())
