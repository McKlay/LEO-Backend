"""
CSV export module for benchmark results — Milestone 6a.

Three export products:

* Expert evaluation CSV (§5.1) — blinded, randomized, columns for human scoring.
* Multi-turn conversation history CSV (§5.2) — full dialog per query–variant.
* Raw results CSV (§5.3) — all runs × all automated metrics.

Usage (programmatic)::

    from tests.benchmark.exporters.csv_exporter import CSVExporter
    exporter = CSVExporter(input_dir=Path("results/run_001"), output_dir=Path("results/exports"))
    exporter.export_raw()
    exporter.export_expert_blind()   # writes expert CSV + blinding mapping
    exporter.export_multiturn()

Usage (CLI)::

    python -m tests.benchmark.exporters.csv_exporter \\
        --input results/run_001 \\
        --output results/exports \\
        [--expert-blind]
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import string
from dataclasses import fields as dc_fields
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Expert-evaluation variant filter ──────────────────────────────────────────
EXPERT_VARIANTS: List[str] = ["llm_only", "stage2_only", "full_pipeline"]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_traces(input_dir: Path) -> List[Dict[str, Any]]:
    """
    Load all QueryTrace JSON files from *input_dir*/partial/ or *input_dir* root.

    Accepts both the flat dump (one JSON per trace) and a consolidated
    ``results.json`` list produced by the runner.

    Args:
        input_dir: Directory containing benchmark result files.

    Returns:
        List of trace dicts sorted by (query_id, variant_name).
    """
    traces: List[Dict[str, Any]] = []

    # Prefer consolidated file if present
    consolidated = input_dir / "results.json"
    if consolidated.exists():
        with consolidated.open(encoding="utf-8") as fh:
            data = json.load(fh)
        # Allow both a flat list and a dict keyed by variant
        if isinstance(data, list):
            traces = data
        elif isinstance(data, dict):
            for variant_traces in data.values():
                traces.extend(variant_traces)
    else:
        # Fall back to partial/ directory — one JSON per query–variant pair
        partial_dir = input_dir / "partial"
        search_dir = partial_dir if partial_dir.exists() else input_dir
        for p in sorted(search_dir.glob("*.json")):
            try:
                with p.open(encoding="utf-8") as fh:
                    obj = json.load(fh)
                if isinstance(obj, list):
                    traces.extend(obj)
                elif isinstance(obj, dict):
                    traces.append(obj)
            except (json.JSONDecodeError, OSError):
                continue

    traces.sort(key=lambda t: (t.get("query_id", ""), t.get("variant_name", "")))
    return traces


def _random_label_map(variant_names: List[str], seed: Optional[int] = None) -> Dict[str, str]:
    """
    Assign a random single-letter blinded label to each variant in
    *variant_names*.

    Labels are drawn from the uppercase alphabet and assigned without
    repetition.  The order of labels is randomized so the mapping is not
    trivially deducible from alphabetical ordering.

    Args:
        variant_names: List of canonical variant names to blind.
        seed: Optional RNG seed for reproducibility.

    Returns:
        Dict mapping canonical variant name → blinded label (e.g. "X").
    """
    rng = random.Random(seed)
    alphabet = list(string.ascii_uppercase)
    rng.shuffle(alphabet)
    return {name: alphabet[i] for i, name in enumerate(variant_names)}


def _safe_json(obj: Any) -> str:
    """Serialize *obj* to a JSON string or return '' on failure."""
    if obj is None:
        return ""
    try:
        return json.dumps(obj, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(obj)


# ── CSVExporter ────────────────────────────────────────────────────────────────

class CSVExporter:
    """
    Exports benchmark results from a completed run directory.

    Attributes:
        input_dir: Directory containing runner output (partial/ JSONs or results.json).
        output_dir: Destination directory for generated CSV files.
    """

    def __init__(self, input_dir: Path, output_dir: Path) -> None:
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._traces: Optional[List[Dict[str, Any]]] = None

    @property
    def traces(self) -> List[Dict[str, Any]]:
        if self._traces is None:
            self._traces = _load_traces(self.input_dir)
        return self._traces

    # ── 5.1 Expert Evaluation CSV ──────────────────────────────────────────────

    def export_expert_blind(
        self,
        seed: Optional[int] = 42,
    ) -> Tuple[Path, Path]:
        """
        Write a blinded, shuffled expert evaluation CSV and a separate
        blinding-mapping JSON.

        Only traces for EXPERT_VARIANTS (llm_only, stage2_only, full_pipeline)
        are included.

        Args:
            seed: RNG seed for reproducible blinding / row shuffling.

        Returns:
            (csv_path, mapping_path) — paths of the two written files.
        """
        rng = random.Random(seed)

        expert_traces = [
            t for t in self.traces
            if t.get("variant_name") in EXPERT_VARIANTS
        ]
        if not expert_traces:
            raise ValueError(
                f"No traces found for expert variants {EXPERT_VARIANTS} in {self.input_dir}"
            )

        label_map = _random_label_map(EXPERT_VARIANTS, seed=seed)
        rows = []
        eval_counter = 1

        for trace in expert_traces:
            variant = trace.get("variant_name", "")
            config_label = label_map.get(variant, variant)

            conv_history = trace.get("gold_chunks", [])  # placeholder; real field below
            # Build conversation history string for multi-turn queries
            conv_hist_str = ""
            if trace.get("is_multiturn"):
                # conversation_history is not stored in QueryTrace directly;
                # we surface prior turn context from the benchmark query metadata
                # if the runner injected it into the trace's query_text context.
                conv_hist_str = trace.get("conversation_history_json", "")

            row = {
                "eval_id": f"E{eval_counter:04d}",
                "query_id": trace.get("query_id", ""),
                "query_text": trace.get("query_text", ""),
                "language": trace.get("language", ""),
                "query_type": "multi_turn" if trace.get("is_multiturn") else "single_turn",
                "is_ambiguous": str(trace.get("is_ambiguous", False)).lower(),
                "topic": trace.get("topic", ""),
                "conversation_history": conv_hist_str,
                "config_label": config_label,
                # Turn 4 answer — used for Tables 6, 7, 9, 10
                "system_answer": trace.get("generated_content", ""),
                "reference_answer": trace.get("reference_answer", ""),
                "gold_article_refs": _safe_json(trace.get("gold_article_refs", [])),
                # Phase 2 columns for multi-turn rows (Table 8)
                "system_answer_turn6": trace.get("turn6_generated_answer", "") if trace.get("is_multiturn") else "",
                "turn6_reference_answer": trace.get("turn6_reference_answer", "") if trace.get("is_multiturn") else "",
                # Expert-fill columns (empty)
                "legal_accuracy_score": "",
                "hallucination_present": "",
                "citation_fidelity_notes": "",
                "clarification_quality": "" if not trace.get("is_ambiguous") else "",
                "notes": "",
            }
            rows.append(row)
            eval_counter += 1

        rng.shuffle(rows)

        csv_path = self.output_dir / "expert_evaluation.csv"
        fieldnames = list(rows[0].keys()) if rows else []
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        mapping_path = self.output_dir / "expert_blinding_mapping.json"
        with mapping_path.open("w", encoding="utf-8") as fh:
            json.dump(
                {"label_to_variant": {v: k for k, v in label_map.items()},
                 "variant_to_label": label_map,
                 "seed": seed},
                fh,
                indent=2,
                ensure_ascii=False,
            )

        return csv_path, mapping_path

    # ── 5.2 Multi-turn Conversation History CSV ──────────────────────────────

    def export_multiturn(self, label_map: Optional[Dict[str, str]] = None) -> Path:
        """
        Write a per-turn conversation history CSV for all multi-turn traces.

        Each row is one message turn.  Config labels can optionally be
        blinded using the same *label_map* produced during expert export.

        Args:
            label_map: Optional variant → blinded label mapping.

        Returns:
            Path to the written CSV file.
        """
        fieldnames = [
            "query_id", "variant", "turn_number", "role", "content",
        ]
        csv_path = self.output_dir / "multiturn_history.csv"

        rows: List[Dict[str, str]] = []
        for trace in self.traces:
            if not trace.get("is_multiturn"):
                continue

            variant = trace.get("variant_name", "")
            blinded = label_map.get(variant, variant) if label_map else variant
            query_id = trace.get("query_id", "")

            # Inject prior turns if stored
            history_json = trace.get("conversation_history_json", "")
            if history_json:
                try:
                    history = json.loads(history_json)
                except (json.JSONDecodeError, TypeError):
                    history = []
                for idx, turn in enumerate(history, start=1):
                    rows.append({
                        "query_id": query_id,
                        "variant": blinded,
                        "turn_number": str(idx),
                        "role": turn.get("role", ""),
                        "content": turn.get("text", turn.get("content", "")),
                    })

            # Final user message
            turn_num = len(json.loads(history_json)) + 1 if history_json else 1
            rows.append({
                "query_id": query_id,
                "variant": blinded,
                "turn_number": str(turn_num),
                "role": "user",
                "content": trace.get("query_text", ""),
            })
            # System response
            rows.append({
                "query_id": query_id,
                "variant": blinded,
                "turn_number": str(turn_num + 1),
                "role": "assistant",
                "content": trace.get("generated_content", ""),
            })

        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        return csv_path

    # ── 5.3 Raw Results CSV ────────────────────────────────────────────────────

    def export_raw(self) -> Path:
        """
        Write a complete raw results CSV — all traces × all automated metrics.

        Metric values are read directly from the trace dict (set by scorers
        after the benchmark run) or default to empty string if absent.

        Returns:
            Path to the written CSV file.
        """
        fieldnames = [
            "query_id", "variant", "language", "query_type", "is_ambiguous",
            "topic", "retrieval_target",
            # Stage outputs
            "retrieved_chunks",
            # Retrieval metrics
            "recall_at_3", "recall_at_5", "recall_at_10",
            "hit_rate_at_3", "hit_rate_at_5", "hit_rate_at_10",
            "mrr",
            # Answer quality
            "token_f1", "rouge_l", "exact_match",
            # Citation
            "citation_precision", "citation_recall", "citation_f1",
            # RAG Triad
            "context_relevance", "groundedness", "answer_relevance",
            # Clarification / timing
            "was_clarification", "total_time_ms",
            # Text content
            "generated_answer", "reference_answer",
        ]

        csv_path = self.output_dir / "raw_results.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for trace in self.traces:
                scores: Dict[str, Any] = trace.get("scores", {})
                total_ms = (
                    (trace.get("processing_time_s") or 0.0) * 1000
                )
                row = {
                    "query_id": trace.get("query_id", ""),
                    "variant": trace.get("variant_name", ""),
                    "language": trace.get("language", ""),
                    "query_type": "multi_turn" if trace.get("is_multiturn") else "single_turn",
                    "is_ambiguous": str(trace.get("is_ambiguous", False)).lower(),
                    "topic": trace.get("topic", ""),
                    "retrieval_target": trace.get("retrieval_target", ""),
                    "retrieved_chunks": _safe_json(trace.get("retrieved_chunk_ids_per_k", {})),
                    "recall_at_3": scores.get("recall@3", ""),
                    "recall_at_5": scores.get("recall@5", ""),
                    "recall_at_10": scores.get("recall@10", ""),
                    "hit_rate_at_3": scores.get("hit_rate@3", ""),
                    "hit_rate_at_5": scores.get("hit_rate@5", ""),
                    "hit_rate_at_10": scores.get("hit_rate@10", ""),
                    "mrr": scores.get("mrr", ""),
                    "token_f1": scores.get("token_f1", ""),
                    "rouge_l": scores.get("rouge_l", ""),
                    "exact_match": scores.get("exact_match", ""),
                    "citation_precision": scores.get("citation_precision", ""),
                    "citation_recall": scores.get("citation_recall", ""),
                    "citation_f1": scores.get("citation_f1", ""),
                    "context_relevance": scores.get("context_relevance", ""),
                    "groundedness": scores.get("groundedness", ""),
                    "answer_relevance": scores.get("answer_relevance", ""),
                    "was_clarification": str(trace.get("is_clarification_response", False)).lower(),
                    "total_time_ms": f"{total_ms:.1f}" if total_ms else "",
                    "generated_answer": trace.get("generated_content", ""),
                    "reference_answer": trace.get("reference_answer", ""),
                }
                writer.writerow(row)

        return csv_path


# ── CLI ────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tests.benchmark.exporters.csv_exporter",
        description="Export benchmark results to CSV files.",
    )
    parser.add_argument(
        "--input", required=True, type=Path,
        help="Path to benchmark run output directory (contains partial/ or results.json).",
    )
    parser.add_argument(
        "--output", required=True, type=Path,
        help="Destination directory for generated CSV files.",
    )
    parser.add_argument(
        "--expert-blind", action="store_true",
        help="Also generate blinded expert evaluation CSV + mapping file.",
    )
    parser.add_argument(
        "--multiturn", action="store_true",
        help="Also generate multi-turn conversation history CSV.",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="RNG seed for blinding / row shuffling (default: 42).",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    exporter = CSVExporter(input_dir=args.input, output_dir=args.output)

    raw_path = exporter.export_raw()
    print(f"Raw results CSV:       {raw_path}")

    label_map: Optional[Dict[str, str]] = None
    if args.expert_blind:
        csv_path, mapping_path = exporter.export_expert_blind(seed=args.seed)
        print(f"Expert evaluation CSV: {csv_path}")
        print(f"Blinding mapping JSON: {mapping_path}")
        # Load mapping for use in multiturn export
        with mapping_path.open(encoding="utf-8") as fh:
            mapping_data = json.load(fh)
        label_map = mapping_data.get("variant_to_label")

    if args.multiturn:
        mt_path = exporter.export_multiturn(label_map=label_map)
        print(f"Multi-turn history CSV:{mt_path}")


if __name__ == "__main__":
    main()

