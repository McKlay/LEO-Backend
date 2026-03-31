"""
Benchmark variant configuration and runtime override utilities.

Defines the 8 pipeline variants to be evaluated and provides utilities
to override settings, reset singletons, and filter queries per variant.
"""
from dataclasses import dataclass
from typing import List, Dict, Any, Literal

from core.config import settings


@dataclass
class VariantConfig:
    """Configuration for a benchmark variant."""
    
    name: str
    retrieval_mode: str  # "dense" | "lexical" | "symbolic" | "hybrid" | "none"
    enable_query_analysis: bool
    enable_translation: bool
    enable_smart_clarification: bool
    query_filter: Literal["all", "non_english", "ambiguous"]
    
    @property
    def display_name(self) -> str:
        """Human-readable name for reports."""
        return self.name.replace("_", " ").title()


# Define all 8 benchmark variants per §2 of the specification
VARIANTS = [
    VariantConfig(
        name="full_pipeline",
        retrieval_mode="hybrid",
        enable_query_analysis=True,
        enable_translation=True,
        enable_smart_clarification=True,
        query_filter="all"
    ),
    VariantConfig(
        name="stage2_only",
        retrieval_mode="hybrid",
        enable_query_analysis=False,
        enable_translation=False,
        enable_smart_clarification=False,
        query_filter="all"
    ),
    VariantConfig(
        name="dense_only",
        retrieval_mode="dense",
        enable_query_analysis=True,
        enable_translation=True,
        enable_smart_clarification=True,
        query_filter="all"
    ),
    VariantConfig(
        name="lexical_only",
        retrieval_mode="lexical",
        enable_query_analysis=True,
        enable_translation=True,
        enable_smart_clarification=True,
        query_filter="all"
    ),
    VariantConfig(
        name="symbolic_only",
        retrieval_mode="symbolic",
        enable_query_analysis=True,
        enable_translation=True,
        enable_smart_clarification=True,
        query_filter="all"
    ),
    VariantConfig(
        name="hybrid_no_translation",
        retrieval_mode="hybrid",
        enable_query_analysis=True,
        enable_translation=False,
        enable_smart_clarification=True,
        query_filter="non_english"
    ),
    VariantConfig(
        name="hybrid_no_clarification",
        retrieval_mode="hybrid",
        enable_query_analysis=True,
        enable_translation=True,
        enable_smart_clarification=False,
        query_filter="ambiguous"
    ),
    VariantConfig(
        name="llm_only",
        retrieval_mode="none",
        enable_query_analysis=False,
        enable_translation=False,
        enable_smart_clarification=False,
        query_filter="all"
    ),
]


# Create a lookup dictionary for quick access by name
VARIANTS_BY_NAME = {v.name: v for v in VARIANTS}


def apply_variant(variant: VariantConfig) -> None:
    """
    Override global settings for the current variant run.
    
    This modifies the `settings` object in-place. Call `reset_singletons()`
    after applying a variant to ensure all cached pipeline components are
    rebuilt with the new configuration.
    
    Args:
        variant: The variant configuration to apply
    """
    settings.retrieval_mode = variant.retrieval_mode
    settings.enable_query_analysis = variant.enable_query_analysis
    settings.enable_translation = variant.enable_translation
    settings.enable_smart_clarification = variant.enable_smart_clarification


def reset_singletons() -> None:
    """
    Clear all cached singletons to force re-initialization with new settings.

    Delegates to `app.containers.cleanup_services()`, which:
    - Calls `cache_clear()` on all @lru_cache-decorated container functions
    - Resets all module-level global singletons (embeddings, LLM, vectorstore, etc.)

    Must be called after `apply_variant()` and before running the pipeline
    to ensure every pipeline object is re-built with the updated settings.
    """
    try:
        from app.containers import cleanup_services
        cleanup_services()
    except ImportError:
        # Containers module not available during isolated unit tests; safe to skip.
        pass


def get_queries_for_variant(
    variant: VariantConfig,
    all_queries: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Filter queries based on variant's query_filter setting.
    
    Args:
        variant: The variant configuration
        all_queries: List of all benchmark queries
        
    Returns:
        Filtered list of queries appropriate for this variant
        
    Query filters:
        - "all": All 100 queries
        - "non_english": Only Filipino and Cebuano queries (50 queries)
        - "ambiguous": Only queries marked as ambiguous (30 queries)
    """
    if variant.query_filter == "all":
        return all_queries
    elif variant.query_filter == "non_english":
        return [
            q for q in all_queries
            if q.get("language", "").lower() in ["fil", "filipino", "ceb", "cebuano"]
        ]
    elif variant.query_filter == "ambiguous":
        return [
            q for q in all_queries
            if q.get("is_ambiguous", False) or q.get("expected_clarification")
        ]
    else:
        raise ValueError(f"Unknown query_filter: {variant.query_filter}")


def get_variant_by_name(name: str) -> VariantConfig:
    """
    Get a variant configuration by name.
    
    Args:
        name: The variant name (e.g., "full_pipeline")
        
    Returns:
        The variant configuration
        
    Raises:
        ValueError: If variant name is not found
    """
    if name not in VARIANTS_BY_NAME:
        available = ", ".join(VARIANTS_BY_NAME.keys())
        raise ValueError(f"Unknown variant '{name}'. Available: {available}")
    return VARIANTS_BY_NAME[name]
