"""
Chart generation for thesis figures — Milestone 6b.

Produces eight publication-quality plots (PDF + PNG at 300 DPI) covering
the evaluation tables defined in §6 of the specification.

Usage (programmatic)::

    from tests.benchmark.exporters.chart_generator import ChartGenerator
    gen = ChartGenerator(input_dir=Path("results/run_001"), output_dir=Path("results/figures"))
    gen.generate_all()

Usage (CLI)::

    python -m tests.benchmark.exporters.chart_generator \\
        --input results/run_001 \\
        --output results/figures
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")  # non-interactive backend for CI / headless environments
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns

# ── Academic palette ───────────────────────────────────────────────────────────
PALETTE = ["#4878CF", "#6ACC65", "#D65F5F", "#B47CC7", "#C4AD66", "#77BEDB", "#AAAAAA", "#F0A500"]
FIGURE_DPI = 300
FIGURE_FORMAT = ("pdf", "png")

sns.set_theme(style="whitegrid", font_scale=1.1)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_traces(input_dir: Path) -> pd.DataFrame:
    """
    Load all trace JSONs from *input_dir* into a flat DataFrame.

    Each trace dict is one row.  Nested ``scores`` sub-dict is flattened
    (e.g. ``scores.recall@5`` → column ``recall_at_5``).

    Args:
        input_dir: Run directory containing partial/ JSONs or results.json.

    Returns:
        DataFrame with one row per query–variant result.
    """
    traces: List[Dict[str, Any]] = []
    consolidated = input_dir / "results.json"
    if consolidated.exists():
        with consolidated.open(encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            traces = data
        elif isinstance(data, dict):
            for v in data.values():
                traces.extend(v)
    else:
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

    rows = []
    for t in traces:
        flat: Dict[str, Any] = {k: v for k, v in t.items() if k != "scores"}
        for metric, val in (t.get("scores") or {}).items():
            col = metric.replace("@", "_at_").replace("-", "_")
            flat[col] = val
        rows.append(flat)

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _save_fig(fig: plt.Figure, output_dir: Path, stem: str) -> None:
    """Save *fig* as both PDF and PNG at 300 DPI."""
    for fmt in FIGURE_FORMAT:
        path = output_dir / f"{stem}.{fmt}"
        fig.savefig(path, dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)


def _require_columns(df: pd.DataFrame, cols: List[str], chart_name: str) -> bool:
    """Return True if all *cols* exist in *df*, else print a warning and return False."""
    missing = [c for c in cols if c not in df.columns]
    if missing:
        print(f"[{chart_name}] Skipped — missing columns: {missing}")
        return False
    return True


# ── ChartGenerator ─────────────────────────────────────────────────────────────

class ChartGenerator:
    """
    Generates all eight thesis figures from a benchmark run directory.

    Each ``chart_*`` method is independent: call individually or call
    :meth:`generate_all` to produce the complete figure set.

    Attributes:
        input_dir: Run directory with result JSONs.
        output_dir: Destination for generated plots.
    """

    # Canonical display names for variants
    VARIANT_LABELS: Dict[str, str] = {
        "full_pipeline": "Hybrid",
        "dense_only": "Dense",
        "lexical_only": "Lexical",
        "symbolic_only": "Symbolic",
        "hybrid_no_translation": "Hybrid (No Trans.)",
        "llm_only": "LLM-only",
        "stage2_only": "Stage 2 Only",
        "hybrid_no_clarification": "No Clarif.",
    }

    def __init__(self, input_dir: Path, output_dir: Path) -> None:
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._df: Optional[pd.DataFrame] = None

    @property
    def df(self) -> pd.DataFrame:
        if self._df is None:
            self._df = _load_traces(self.input_dir)
        return self._df

    def _label(self, variant: str) -> str:
        return self.VARIANT_LABELS.get(variant, variant)

    # ── 6.1 Retrieval Performance Comparison (Table 2) ─────────────────────────

    def chart_retrieval_comparison(self) -> None:
        """
        Grouped bar chart: Dense / Lexical / Symbolic / Hybrid × retrieval metrics.

        Metrics: Recall@3, Recall@5, Recall@10, Hit Rate@5, MRR.
        """
        metrics = ["recall_at_3", "recall_at_5", "recall_at_10", "hit_rate_at_5", "mrr"]
        labels = ["Recall@3", "Recall@5", "Recall@10", "Hit Rate@5", "MRR"]
        variants = ["full_pipeline", "dense_only", "lexical_only", "symbolic_only"]

        if not _require_columns(self.df, metrics + ["variant_name"], "chart_retrieval_comparison"):
            return

        df = self.df[self.df["variant_name"].isin(variants)].copy()
        agg = df.groupby("variant_name")[metrics].mean().reset_index()

        x = np.arange(len(metrics))
        width = 0.18
        fig, ax = plt.subplots(figsize=(10, 5))

        for i, variant in enumerate(variants):
            row = agg[agg["variant_name"] == variant]
            if row.empty:
                continue
            vals = [float(row[m].values[0]) if m in row else 0.0 for m in metrics]
            ax.bar(x + i * width, vals, width, label=self._label(variant), color=PALETTE[i])

        ax.set_xticks(x + width * (len(variants) - 1) / 2)
        ax.set_xticklabels(labels)
        ax.set_ylabel("Score")
        ax.set_title("Retrieval Strategy Comparison (Table 2)")
        ax.set_ylim(0, 1.05)
        ax.legend(loc="upper right")
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))
        fig.tight_layout()
        _save_fig(fig, self.output_dir, "retrieval_comparison")

    # ── 6.2 Retrieval by Target Subset (Table 3) ──────────────────────────────

    def chart_retrieval_by_target(self) -> None:
        """
        Grouped bar chart: MRR per retrieval target subset × retrieval strategy.
        """
        metrics = ["mrr"]
        variants = ["full_pipeline", "dense_only", "lexical_only", "symbolic_only"]
        required = ["variant_name", "retrieval_target", "mrr"]

        if not _require_columns(self.df, required, "chart_retrieval_by_target"):
            return

        df = self.df[self.df["variant_name"].isin(variants)].copy()
        targets = sorted(df["retrieval_target"].dropna().unique())
        if not targets:
            print("[chart_retrieval_by_target] No retrieval_target data found — skipping.")
            return

        agg = df.groupby(["retrieval_target", "variant_name"])["mrr"].mean().unstack(fill_value=0)
        # Reorder columns to canonical variant order
        ordered_cols = [v for v in variants if v in agg.columns]
        agg = agg[ordered_cols]
        agg.columns = [self._label(v) for v in ordered_cols]

        fig, ax = plt.subplots(figsize=(9, 5))
        x = np.arange(len(agg))
        width = 0.8 / len(agg.columns)
        for i, col in enumerate(agg.columns):
            ax.bar(x + i * width, agg[col], width, label=col, color=PALETTE[i])

        ax.set_xticks(x + width * (len(agg.columns) - 1) / 2)
        ax.set_xticklabels(agg.index, rotation=15, ha="right")
        ax.set_ylabel("MRR")
        ax.set_title("MRR by Retrieval Target Subset (Table 3)")
        ax.set_ylim(0, 1.05)
        ax.legend(loc="upper right")
        fig.tight_layout()
        _save_fig(fig, self.output_dir, "retrieval_by_target")

    # ── 6.3 Translation Pivot Impact (Table 4) ────────────────────────────────

    def chart_translation_impact(self) -> None:
        """
        Grouped bar chart with Δ annotations: language × with/without translation.
        """
        required = ["variant_name", "language", "hit_rate_at_5", "recall_at_5"]
        if not _require_columns(self.df, required, "chart_translation_impact"):
            return

        with_trans = ["full_pipeline"]
        no_trans = ["hybrid_no_translation"]

        df = self.df[self.df["variant_name"].isin(with_trans + no_trans)].copy()
        df["group"] = df["variant_name"].map(
            {**{v: "With Translation" for v in with_trans},
             **{v: "No Translation" for v in no_trans}}
        )

        languages = ["en", "fil", "ceb"]
        lang_labels = {"en": "English", "fil": "Filipino", "ceb": "Cebuano"}
        metric = "recall_at_5"
        agg = df.groupby(["language", "group"])[metric].mean().unstack(fill_value=0)

        fig, ax = plt.subplots(figsize=(8, 5))
        x = np.arange(len(languages))
        width = 0.32

        for i, grp in enumerate(["With Translation", "No Translation"]):
            vals = [float(agg.loc[lang, grp]) if lang in agg.index and grp in agg.columns else 0.0
                    for lang in languages]
            bars = ax.bar(x + i * width, vals, width, label=grp, color=PALETTE[i])

            # Δ annotation (With − No)
            if i == 0:
                for j, lang in enumerate(languages):
                    v_with = float(agg.loc[lang, "With Translation"]) if lang in agg.index and "With Translation" in agg.columns else 0.0
                    v_no = float(agg.loc[lang, "No Translation"]) if lang in agg.index and "No Translation" in agg.columns else 0.0
                    delta = v_with - v_no
                    if abs(delta) > 0.001:
                        y_pos = max(v_with, v_no) + 0.02
                        ax.annotate(
                            f"Δ{delta:+.2f}",
                            xy=(x[j] + width / 2, y_pos),
                            ha="center", va="bottom", fontsize=8, color="#333333",
                        )

        ax.set_xticks(x + width / 2)
        ax.set_xticklabels([lang_labels[l] for l in languages])
        ax.set_ylabel("Recall@5")
        ax.set_title("Translation Pivot Impact by Language (Table 4)")
        ax.set_ylim(0, 1.15)
        ax.legend()
        fig.tight_layout()
        _save_fig(fig, self.output_dir, "translation_impact")

    # ── 6.4 Answer Quality Across Configurations (Table 6) ────────────────────

    def chart_answer_quality(self) -> None:
        """
        Grouped bar chart: Config A / B / C × Mean Expert Score / Token F1 / ROUGE-L.
        """
        required = ["variant_name", "token_f1", "rouge_l"]
        if not _require_columns(self.df, required, "chart_answer_quality"):
            return

        config_map = {
            "llm_only": "Config A\n(LLM-only)",
            "stage2_only": "Config B\n(Stage 2 Only)",
            "full_pipeline": "Config C\n(Full Pipeline)",
        }
        metrics = ["token_f1", "rouge_l"]
        metric_labels = ["Token F1", "ROUGE-L"]

        # Include expert score if present
        if "expert_score_normalized" in self.df.columns:
            metrics = ["expert_score_normalized"] + metrics
            metric_labels = ["Mean Expert Score"] + metric_labels

        df = self.df[self.df["variant_name"].isin(config_map)].copy()
        agg = df.groupby("variant_name")[metrics].mean()

        x = np.arange(len(metrics))
        width = 0.25
        fig, ax = plt.subplots(figsize=(9, 5))

        for i, (variant, label) in enumerate(config_map.items()):
            if variant not in agg.index:
                continue
            vals = [float(agg.loc[variant, m]) for m in metrics]
            ax.bar(x + i * width, vals, width, label=label, color=PALETTE[i])

        ax.set_xticks(x + width)
        ax.set_xticklabels(metric_labels)
        ax.set_ylabel("Score")
        ax.set_title("Answer Quality by Pipeline Configuration (Table 6)")
        ax.set_ylim(0, 1.05)
        ax.legend(loc="upper right")
        fig.tight_layout()
        _save_fig(fig, self.output_dir, "answer_quality")

    # ── 6.5 Hallucination & Citation Fidelity (Table 9) ───────────────────────

    def chart_hallucination_citation(self) -> None:
        """
        Grouped bar chart: Config A / B / C ×
        Hallucination Rate / Fabricated Citation Rate / Citation Precision / Citation Recall.
        """
        required = ["variant_name", "citation_precision", "citation_recall"]
        if not _require_columns(self.df, required, "chart_hallucination_citation"):
            return

        config_map = {
            "llm_only": "Config A",
            "stage2_only": "Config B",
            "full_pipeline": "Config C",
        }
        metrics = ["citation_precision", "citation_recall"]
        labels = ["Citation Precision", "Citation Recall"]

        if "hallucination_rate" in self.df.columns:
            metrics = ["hallucination_rate"] + metrics
            labels = ["Hallucination Rate"] + labels

        df = self.df[self.df["variant_name"].isin(config_map)].copy()
        agg = df.groupby("variant_name")[metrics].mean()

        x = np.arange(len(metrics))
        width = 0.25
        fig, ax = plt.subplots(figsize=(9, 5))

        for i, (variant, display) in enumerate(config_map.items()):
            if variant not in agg.index:
                continue
            vals = [float(agg.loc[variant, m]) for m in metrics]
            ax.bar(x + i * width, vals, width, label=display, color=PALETTE[i])

        ax.set_xticks(x + width)
        ax.set_xticklabels(labels)
        ax.set_ylabel("Rate / Score")
        ax.set_title("Hallucination & Citation Fidelity (Table 9)")
        ax.set_ylim(0, 1.05)
        ax.legend()
        fig.tight_layout()
        _save_fig(fig, self.output_dir, "hallucination_citation")

    # ── 6.6 RAG Triad Radar Chart (Table 10) ──────────────────────────────────

    def chart_rag_triad(self) -> None:
        """
        Radar/spider chart: Config B vs Config C on Context Relevance /
        Groundedness / Answer Relevance.
        """
        required = ["variant_name", "context_relevance", "groundedness", "answer_relevance"]
        if not _require_columns(self.df, required, "chart_rag_triad"):
            return

        dims = ["context_relevance", "groundedness", "answer_relevance"]
        dim_labels = ["Context\nRelevance", "Groundedness", "Answer\nRelevance"]
        variants = ["stage2_only", "full_pipeline"]

        df = self.df[self.df["variant_name"].isin(variants)].copy()
        agg = df.groupby("variant_name")[dims].mean()

        N = len(dims)
        angles = [n / float(N) * 2 * np.pi for n in range(N)]
        angles += angles[:1]  # close the polygon

        fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))

        for i, (variant, label) in enumerate([("stage2_only", "Config B"), ("full_pipeline", "Config C")]):
            if variant not in agg.index:
                continue
            vals = [float(agg.loc[variant, d]) for d in dims]
            vals += vals[:1]
            ax.plot(angles, vals, "o-", linewidth=2, label=label, color=PALETTE[i])
            ax.fill(angles, vals, alpha=0.15, color=PALETTE[i])

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(dim_labels, size=10)
        ax.set_ylim(0, 5)
        ax.set_yticks([1, 2, 3, 4, 5])
        ax.set_yticklabels(["1", "2", "3", "4", "5"], size=7)
        ax.set_title("RAG Triad: Config B vs Config C (Table 10)", pad=15)
        ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))
        fig.tight_layout()
        _save_fig(fig, self.output_dir, "rag_triad")

    # ── 6.7 Ablation Heatmap (Table 11) ───────────────────────────────────────

    def chart_ablation_heatmap(self) -> None:
        """
        Heatmap: 8 pipeline variants × key metrics
        (Recall@5, MRR, Token F1, ROUGE-L, Citation Recall).
        """
        metrics = ["recall_at_5", "mrr", "token_f1", "rouge_l", "citation_recall"]
        metric_labels = ["Recall@5", "MRR", "Token F1", "ROUGE-L", "Cit. Recall"]

        required = ["variant_name"] + metrics
        available = [m for m in metrics if m in self.df.columns]
        if not available:
            print("[chart_ablation_heatmap] No metric columns found — skipping.")
            return
        if "variant_name" not in self.df.columns:
            print("[chart_ablation_heatmap] Missing variant_name — skipping.")
            return

        metrics = available
        metric_labels = metric_labels[: len(metrics)]

        agg = self.df.groupby("variant_name")[metrics].mean()
        # Use human-readable row labels
        agg.index = [self._label(v) for v in agg.index]

        fig, ax = plt.subplots(figsize=(9, 5))
        cmap = sns.diverging_palette(10, 133, as_cmap=True)
        sns.heatmap(
            agg,
            ax=ax,
            annot=True,
            fmt=".2f",
            cmap=cmap,
            vmin=0,
            vmax=1,
            linewidths=0.5,
            cbar_kws={"shrink": 0.8},
        )
        ax.set_xticklabels(metric_labels, rotation=0)
        ax.set_ylabel("Variant")
        ax.set_title("Ablation Study — Metric Heatmap (Table 11)")
        fig.tight_layout()
        _save_fig(fig, self.output_dir, "ablation_heatmap")

    # ── 6.8 Per-Topic Performance Breakdown ───────────────────────────────────

    def chart_topic_breakdown(self) -> None:
        """
        Horizontal bar chart: Recall@5 per topic for the Full Pipeline variant.
        """
        required = ["variant_name", "topic", "recall_at_5"]
        if not _require_columns(self.df, required, "chart_topic_breakdown"):
            return

        df = self.df[self.df["variant_name"] == "full_pipeline"].copy()
        agg = df.groupby("topic")["recall_at_5"].mean().sort_values(ascending=True)

        if agg.empty:
            print("[chart_topic_breakdown] No full_pipeline topic data found — skipping.")
            return

        fig, ax = plt.subplots(figsize=(9, max(4, len(agg) * 0.38)))
        bars = ax.barh(agg.index, agg.values, color=PALETTE[0], edgecolor="white")
        ax.set_xlabel("Recall@5")
        ax.set_title("Per-Topic Recall@5 — Full Pipeline (Table 12)")
        ax.set_xlim(0, 1.0)
        ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))
        for bar, val in zip(bars, agg.values):
            ax.text(val + 0.01, bar.get_y() + bar.get_height() / 2,
                    f"{val:.2f}", va="center", fontsize=8)
        fig.tight_layout()
        _save_fig(fig, self.output_dir, "topic_breakdown")

    # ── generate_all ───────────────────────────────────────────────────────────

    def generate_all(self) -> None:
        """Run all eight chart methods in sequence."""
        charts = [
            ("6.1 Retrieval Comparison", self.chart_retrieval_comparison),
            ("6.2 Retrieval by Target", self.chart_retrieval_by_target),
            ("6.3 Translation Impact", self.chart_translation_impact),
            ("6.4 Answer Quality", self.chart_answer_quality),
            ("6.5 Hallucination & Citation", self.chart_hallucination_citation),
            ("6.6 RAG Triad Radar", self.chart_rag_triad),
            ("6.7 Ablation Heatmap", self.chart_ablation_heatmap),
            ("6.8 Topic Breakdown", self.chart_topic_breakdown),
        ]
        for name, fn in charts:
            try:
                fn()
                print(f"  [OK] {name}")
            except Exception as exc:  # noqa: BLE001
                print(f"  [FAIL] {name}: {exc}")


# ── CLI ────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tests.benchmark.exporters.chart_generator",
        description="Generate thesis figures from benchmark results.",
    )
    parser.add_argument(
        "--input", required=True, type=Path,
        help="Path to benchmark run output directory.",
    )
    parser.add_argument(
        "--output", required=True, type=Path,
        help="Destination directory for generated figures.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    gen = ChartGenerator(input_dir=args.input, output_dir=args.output)
    gen.generate_all()
    print(f"\nFigures written to: {args.output}")


if __name__ == "__main__":
    main()

