"""
Result collector for benchmark runs.

Captures pipeline outputs from SSE events and assembles QueryTrace objects
for downstream analysis and scoring.

Usage:
    collector = ResultCollector(output_dir=Path("results/run_001"))
    collector.start_trace(query, variant_name)
    for event in stream:
        collector.process_event(event)
    trace = collector.finalize_trace()
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class QueryTrace:
    """
    Full pipeline trace for a single query–variant pair.

    Populated progressively either from SSE events (full mode) or from
    direct pipeline calls (analysis_only / retrieval_only modes).
    Stores Stage 1, 2, 3 outputs alongside gold standard fields for
    downstream automated and human scoring.
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    query_id: str
    variant_name: str
    turn1_query: str         # original query text from benchmark JSON (always Turn 1)
    language: str

    # ── Query Metadata ────────────────────────────────────────────────────────
    query_type: str = "single_turn"          # "single_turn" | "multi_turn"
    is_multiturn: bool = False
    is_ambiguous: bool = False
    topic: Optional[str] = None
    retrieval_target: Optional[str] = None   # symbolic | lexical | dense | hybrid
    prior_turn_count: int = 0                # number of turns injected into memory
    turn3_query: Optional[str] = None        # final user turn sent to pipeline (multi-turn only; null for single-turn)
    conversation_history: List[Dict[str, str]] = field(default_factory=list)  # full conversation turns for tracing

    # ── Stage 1: Query Analysis ───────────────────────────────────────────────
    normalized_query_en: Optional[str] = None
    original_language: Optional[str] = None
    needs_clarification: Optional[bool] = None
    clarification_question: Optional[str] = None
    is_meta_conversational: Optional[bool] = None
    out_of_scope: Optional[bool] = None
    legal_concepts: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    articles_extracted: List[str] = field(default_factory=list)
    analysis_time_s: Optional[float] = None

    # ── Stage 2: Retrieval ────────────────────────────────────────────────────
    # Per-K results from separate calls (RRF-correct; populated in retrieval_only mode).
    retrieved_chunk_ids_per_k: Dict[int, List[str]] = field(default_factory=dict)
    retrieved_scores_per_k: Dict[int, List[float]] = field(default_factory=dict)
    retrieval_time_s: Optional[float] = None
    retrieval_count: Optional[int] = None
    avg_retrieval_confidence: Optional[float] = None

    # ── Stage 3: Generation ───────────────────────────────────────────────────
    generated_response: Optional[str] = None  # turn2_response (single-turn) / turn4_response (multi-turn) in JSON
    generated_citations: List[Dict[str, Any]] = field(default_factory=list)
    generation_time_s: Optional[float] = None
    processing_time_s: Optional[float] = None
    is_clarification_response: bool = False

    # ── Gold Standard ────────────────────────────────────────────────────────
    turn2_clarification_response: Optional[str] = None  # gold clarification question (ambiguous multi-turn only)
    gold_chunks: List[str] = field(default_factory=list)
    gold_article_refs: List[str] = field(default_factory=list)
    reference_answer: Optional[str] = None

    # ── Phase 2: Turn 5–6 (multi-turn queries only) ───────────────────────────
    turn5_query: Optional[str] = None
    turn6_response: Optional[str] = None
    turn6_extracted_citations: Optional[List[str]] = None
    gold_chunks_turn6: Optional[List[str]] = None
    gold_article_refs_turn6: Optional[List[str]] = None
    turn6_reference_answer: Optional[str] = None

    # ── Errors / Timestamps ───────────────────────────────────────────────────
    error: Optional[str] = None
    timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize trace to a JSON-serializable dict.

        ``generated_response`` is emitted as ``turn2_response`` for single-turn
        queries and ``turn4_response`` for multi-turn queries so the JSON output
        reflects the logical turn structure of the conversation.
        """
        d = asdict(self)
        resp_key = "turn2_response" if self.query_type == "single_turn" else "turn4_response"
        d[resp_key] = d.pop("generated_response", None)
        return d

    @classmethod
    def from_query(
        cls,
        query: Dict[str, Any],
        variant_name: str,
        turn3_query: Optional[str] = None,
        prior_turn_count: int = 0,
    ) -> "QueryTrace":
        """
        Initialize a QueryTrace from a benchmark query record.

        Args:
            query: Dict from benchmark-queries.json
            variant_name: Pipeline variant being evaluated
            turn3_query: Final user turn sent to pipeline; populated for multi-turn
                queries only (the resolved clarification response). None for single-turn.
            prior_turn_count: Number of prior conversation turns injected into memory.
        """
        query_type = query.get("query_type", "single_turn")
        return cls(
            query_id=query["query_id"],
            variant_name=variant_name,
            turn1_query=query["query_text"],  # Always store Turn 1 (original query)
            language=query.get("language", "en"),
            query_type=query_type,
            is_multiturn=query_type == "multi_turn",
            is_ambiguous=query.get("is_ambiguous", False),
            topic=query.get("topic"),
            retrieval_target=query.get("retrieval_target"),
            prior_turn_count=prior_turn_count,
            turn3_query=turn3_query if query_type == "multi_turn" else None,
            conversation_history=query.get("conversation_history", []),
            turn2_clarification_response=query.get("expected_clarification"),
            gold_chunks=query.get("gold_chunks", []),
            gold_article_refs=query.get("gold_article_refs", []),
            reference_answer=query.get("reference_answer"),
            turn5_query=query.get("turn5_query"),
            gold_chunks_turn6=query.get("gold_chunks_turn6"),
            gold_article_refs_turn6=query.get("gold_article_refs_turn6"),
            turn6_reference_answer=query.get("turn6_reference_answer"),
            timestamp=datetime.utcnow().isoformat(),
        )


class ResultCollector:
    """
    Collects and persists benchmark results from pipeline events.

    Handles progressive population of QueryTrace from SSE events (full mode)
    or direct pipeline calls (analysis_only / retrieval_only modes).
    Writes one partial JSON file per query–variant pair so interrupted runs
    can be resumed without losing completed work.
    """

    def __init__(self, output_dir: Path):
        """
        Args:
            output_dir: Root directory for writing partial and final results.
        """
        self.output_dir = output_dir
        self.partial_dir = output_dir / "partial"
        self.partial_dir.mkdir(parents=True, exist_ok=True)

        self.current_trace: Optional[QueryTrace] = None
        self._content_chunks: List[str] = []
        self._turn6_chunks: List[str] = []
        self.variant_results: Dict[str, List[QueryTrace]] = {}

        logger.info(f"ResultCollector initialized: output_dir={output_dir}")

    # ── Trace lifecycle ────────────────────────────────────────────────────────

    def start_trace(
        self,
        query: Dict[str, Any],
        variant_name: str,
        turn3_query: Optional[str] = None,
        prior_turn_count: int = 0,
    ) -> QueryTrace:
        """
        Begin collecting results for a new query–variant pair.

        Args:
            query: Benchmark query dict
            variant_name: Variant being evaluated
            turn3_query: Final user turn sent to pipeline (multi-turn only)
            prior_turn_count: Number of prior turns injected into memory

        Returns:
            Fresh QueryTrace for this pair
        """
        self.current_trace = QueryTrace.from_query(
            query, variant_name,
            turn3_query=turn3_query,
            prior_turn_count=prior_turn_count,
        )
        self._content_chunks = []
        self._turn6_chunks = []
        return self.current_trace

    def process_event(self, event: Dict[str, Any]) -> None:
        """
        Parse an SSE event dict and update the current trace.

        Handles all event types produced by process_message_stream:
          - status         step progress (not recorded as metrics)
          - metadata       retrieval timing and count
          - content_chunk  streaming text chunk (accumulated for full content)
          - citations      citation objects
          - complete       final message with full metadata
          - error          pipeline error

        Args:
            event: Dict with 'type' and 'data' keys
        """
        if self.current_trace is None:
            logger.warning("process_event called without an active trace")
            return

        event_type = event.get("type")
        data = event.get("data", {})

        if event_type == "status":
            pass  # Step progress only; not recorded as a metric

        elif event_type == "analysis":
            self.current_trace.normalized_query_en = data.get("normalized_query_en")
            self.current_trace.original_language = data.get("original_language")
            self.current_trace.needs_clarification = data.get("needs_clarification")
            self.current_trace.clarification_question = data.get("clarification_question")
            self.current_trace.is_meta_conversational = data.get("is_meta_conversational")
            self.current_trace.out_of_scope = data.get("out_of_scope")
            self.current_trace.legal_concepts = data.get("legal_concepts", [])
            self.current_trace.keywords = data.get("keywords", [])
            self.current_trace.articles_extracted = data.get("articles_extracted", [])
            self.current_trace.analysis_time_s = data.get("analysis_time")

        elif event_type == "metadata":
            self.current_trace.retrieval_time_s = data.get("retrieval_time")
            self.current_trace.retrieval_count = data.get("retrieval_count")
            self.current_trace.avg_retrieval_confidence = data.get("avg_confidence")
            # Populate retrieved chunk IDs from the metadata event (full mode)
            chunk_ids = data.get("retrieved_chunk_ids", [])
            if chunk_ids:
                k = len(chunk_ids)
                self.current_trace.retrieved_chunk_ids_per_k[k] = chunk_ids

        elif event_type == "content_chunk":
            self._content_chunks.append(data.get("chunk", ""))

        elif event_type == "citations":
            self.current_trace.generated_citations = data.get("citations", [])

        elif event_type == "complete":
            meta = data.get("metadata", {})
            # Prefer assembled full content from chunks; fall back to event content field
            assembled = "".join(self._content_chunks)
            self.current_trace.generated_response = assembled or data.get("content")
            # Citations may have been populated by the prior 'citations' event;
            # the 'complete' event carries the authoritative copy.
            self.current_trace.generated_citations = data.get(
                "citations", self.current_trace.generated_citations
            )
            self.current_trace.is_clarification_response = meta.get("is_clarification", False)
            self.current_trace.is_meta_conversational = meta.get("is_meta_conversational")
            self.current_trace.generation_time_s = meta.get("generation_time")
            self.current_trace.processing_time_s = meta.get("processing_time")
            if meta.get("analysis_time"):
                self.current_trace.analysis_time_s = meta.get("analysis_time")

        elif event_type == "error":
            self.current_trace.error = data.get("error", "Unknown error")
            logger.warning(
                f"Pipeline error for "
                f"{self.current_trace.query_id}/{self.current_trace.variant_name}: "
                f"{self.current_trace.error}"
            )

        else:
            logger.debug(f"Unknown SSE event type: {event_type}")

    def process_event_phase2(self, event: Dict[str, Any]) -> None:
        """
        Parse an SSE event for Phase 2 (Turn 6) and update Phase 2 trace fields.

        Called during _run_phase2 execution (Turn 5 → Turn 6 exchange).
        Accumulates content chunks and on 'complete' assembles
        turn6_response and extracts turn6_extracted_citations via regex.
        Metadata and citation-object events are intentionally ignored for Phase 2
        — Table 8 scores answer quality only (Decision 2).

        Args:
            event: Dict with 'type' and 'data' keys
        """
        if self.current_trace is None:
            logger.warning("process_event_phase2 called without an active trace")
            return

        event_type = event.get("type")
        data = event.get("data", {})

        if event_type == "content_chunk":
            self._turn6_chunks.append(data.get("chunk", ""))

        elif event_type == "complete":
            from tests.benchmark.scorers.citation import extract_citations
            assembled = "".join(self._turn6_chunks)
            self.current_trace.turn6_response = assembled or data.get("content")
            if self.current_trace.turn6_response:
                self.current_trace.turn6_extracted_citations = extract_citations(
                    self.current_trace.turn6_response
                )

        elif event_type == "error":
            logger.warning(
                f"Phase 2 pipeline error for "
                f"{self.current_trace.query_id}/{self.current_trace.variant_name}: "
                f"{data.get('error', 'Unknown error')}"
            )

    def record_analysis(self, analysis: Any, analysis_time_s: float = 0.0) -> None:
        """
        Populate Stage 1 fields from a QueryAnalysis object.

        Used by analysis_only and retrieval_only modes that call the analysis
        pipeline directly rather than through the SSE orchestrator.

        Args:
            analysis: QueryAnalysis result from QueryAnalysisPipeline.analyze()
            analysis_time_s: Wall-clock time for the analysis call
        """
        if self.current_trace is None:
            return

        self.current_trace.normalized_query_en = analysis.normalized_query_en
        self.current_trace.original_language = analysis.original_language
        self.current_trace.needs_clarification = analysis.needs_clarification
        self.current_trace.clarification_question = analysis.clarification_question
        self.current_trace.is_meta_conversational = analysis.is_meta_conversational
        self.current_trace.out_of_scope = analysis.out_of_scope
        self.current_trace.legal_concepts = list(analysis.legal_concepts)
        self.current_trace.keywords = list(analysis.keywords)
        self.current_trace.articles_extracted = list(analysis.articles)
        self.current_trace.analysis_time_s = analysis_time_s

    @staticmethod
    def _resolve_chunk_id(result: Any) -> str:
        """
        Return the canonical ``chunk_id`` for a QueryResult.

        The ``chunk_id`` is the stable identifier declared in every chunk's
        YAML frontmatter and stored as ``metadata.chunk_id`` in the vector
        store.  It is always present and does not depend on file-path
        reconstruction, making it the preferred comparison key against
        ``gold_chunks`` in the benchmark dataset.

        Fallback chain (for chunks ingested before frontmatter standardisation):
        1. ``metadata.chunk_id``   → e.g. ``dole_handbook_2023_min_wage_eemr_formulas``
        2. ``metadata.short_name`` + ``metadata.file_stem`` → path form
        3. Raw DB id (UUID — cannot match gold, but avoids empty strings)
        """
        meta = getattr(result, "metadata", None) or {}
        chunk_id = meta.get("chunk_id", "")
        if chunk_id:
            return chunk_id
        # Fallback: reconstruct source-path form for pre-standardised chunks
        short_name = meta.get("short_name", "")
        file_stem = meta.get("file_stem", "")
        if short_name and file_stem:
            return f"{short_name}/{file_stem}.md"
        return result.id

    def record_retrieval_per_k(
        self,
        results_by_k: Dict[int, Any],
        retrieval_time_s: float = 0.0,
    ) -> None:
        """
        Populate per-K retrieval fields from separate per-K retrieval calls.

        Stores chunk IDs and scores in retrieved_chunk_ids_per_k /
        retrieved_scores_per_k for RRF-correct metric computation.
        Summary stats (retrieval_count, retrieval_time_s, avg_retrieval_confidence)
        are derived from the max-K results for logging and raw CSV output.

        Args:
            results_by_k: Dict mapping K → List[QueryResult] from separate calls
            retrieval_time_s: Total wall-clock time across all K-value calls
        """
        if self.current_trace is None:
            return

        for k, results in results_by_k.items():
            self.current_trace.retrieved_chunk_ids_per_k[k] = [
                self._resolve_chunk_id(r) for r in results
            ]
            self.current_trace.retrieved_scores_per_k[k] = [r.score for r in results]

        # Set summary stats from max-K for logging and raw CSV output.
        if results_by_k:
            max_k = max(results_by_k.keys())
            max_results = results_by_k[max_k]
            self.current_trace.retrieval_count = len(max_results)
            self.current_trace.retrieval_time_s = retrieval_time_s
            if max_results:
                self.current_trace.avg_retrieval_confidence = (
                    sum(r.score for r in max_results) / len(max_results)
                )

    def finalize_trace(self, persist: bool = True) -> QueryTrace:
        """
        Finalize the current trace and optionally write it to disk.

        Args:
            persist: If True, write a partial JSON file for resume support.

        Returns:
            The finalized QueryTrace

        Raises:
            RuntimeError: If no trace is currently active
        """
        if self.current_trace is None:
            raise RuntimeError("finalize_trace() called without an active trace")

        trace = self.current_trace
        variant = trace.variant_name

        if variant not in self.variant_results:
            self.variant_results[variant] = []
        self.variant_results[variant].append(trace)

        if persist:
            variant_dir = self.partial_dir / variant
            variant_dir.mkdir(parents=True, exist_ok=True)
            partial_path = variant_dir / f"{trace.query_id}.json"
            partial_path.write_text(
                json.dumps(trace.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.debug(f"Persisted partial result: {partial_path}")

        self.current_trace = None
        self._content_chunks = []
        return trace

    # ── Variant-level operations ───────────────────────────────────────────────

    def finalize_variant(self, variant_name: str) -> List[QueryTrace]:
        """
        Seal results for a completed variant and write a consolidated JSON file.

        Args:
            variant_name: Name of the completed variant

        Returns:
            All QueryTrace objects for this variant
        """
        traces = self.variant_results.get(variant_name, [])

        results_path = self.output_dir / f"{variant_name}_results.json"
        payload = {
            "variant": variant_name,
            "query_count": len(traces),
            "finalized_at": datetime.utcnow().isoformat(),
            "traces": [t.to_dict() for t in traces],
        }
        results_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(
            f"Finalized variant '{variant_name}': {len(traces)} traces → {results_path}"
        )
        return traces

    # ── Resume support ────────────────────────────────────────────────────────

    def is_completed(self, query_id: str, variant_name: str) -> bool:
        """
        Return True if a partial result file exists for this query–variant pair.

        Args:
            query_id: Query identifier (e.g. "Q007")
            variant_name: Variant name
        """
        return (self.partial_dir / variant_name / f"{query_id}.json").exists()

    def load_partial_results(self, variant_name: str) -> List[QueryTrace]:
        """
        Load previously persisted partial results for a variant.

        Restores already-computed traces into memory so the runner can
        report them in the final variant summary without re-running.

        Args:
            variant_name: Variant to load results for

        Returns:
            List of loaded QueryTrace objects (may be empty)
        """
        variant_dir = self.partial_dir / variant_name
        if not variant_dir.exists():
            return []

        traces: List[QueryTrace] = []
        fields = QueryTrace.__dataclass_fields__

        for result_file in sorted(variant_dir.glob("*.json")):
            try:
                data = json.loads(result_file.read_text(encoding="utf-8"))
                trace = QueryTrace(**{k: v for k, v in data.items() if k in fields})
                traces.append(trace)
            except Exception as e:
                logger.warning(f"Failed to load partial result {result_file}: {e}")

        if traces:
            logger.info(
                f"Loaded {len(traces)} partial results for variant '{variant_name}'"
            )
            if variant_name not in self.variant_results:
                self.variant_results[variant_name] = []
            self.variant_results[variant_name].extend(traces)

        return traces
