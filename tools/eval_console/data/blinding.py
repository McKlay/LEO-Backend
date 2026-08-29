import random
from typing import Dict, List


def get_display_order(query_id: str) -> List[str]:
    """Return config labels ['Q','M','J'] in a deterministic per-query shuffle.

    Both reviewers see the same column order for each query because the shuffle
    is seeded by the numeric portion of query_id.
    """
    numeric = int("".join(c for c in query_id if c.isdigit()) or 0)
    rng = random.Random(numeric)
    labels = ["Q", "M", "J"]
    rng.shuffle(labels)
    return labels


def config_to_system_map(query_id: str) -> Dict[str, str]:
    """Return {config_label: 'System A'/'System B'/'System C'} for one query."""
    order = get_display_order(query_id)
    return {label: f"System {chr(65 + i)}" for i, label in enumerate(order)}
