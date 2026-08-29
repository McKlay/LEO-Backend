import csv
import json
from pathlib import Path
from typing import Dict, List, Optional

_REPO_ROOT = Path(__file__).parent.parent.parent.parent
CSV_PATH = _REPO_ROOT / "tests/benchmark/results/exports/expert_evaluation.csv"
BLINDING_PATH = _REPO_ROOT / "tests/benchmark/results/exports/expert_blinding_mapping.json"
BENCHMARK_JSON_PATH = _REPO_ROOT / "tests/benchmark/data/benchmark-queries.json"

# In-memory stores populated at startup
_eval_store: Dict[str, dict] = {}          # eval_id  → row dict
_query_store: Dict[str, List[dict]] = {}   # query_id → [row, row, row]
_query_order: List[str] = []               # stable insertion-order list of query_ids
_turn5_lookup: Dict[str, str] = {}         # query_id → turn5_query text


def load_data() -> None:
    global _eval_store, _query_store, _query_order, _turn5_lookup
    _eval_store.clear()
    _query_store.clear()
    _query_order.clear()
    _turn5_lookup.clear()

    # Load turn5_query from the original benchmark JSON (not in expert_evaluation.csv)
    if BENCHMARK_JSON_PATH.exists():
        with open(BENCHMARK_JSON_PATH, encoding="utf-8") as f:
            bq = json.load(f)
        for q in bq.get("queries", []):
            qid = q.get("query_id", "")
            t5 = q.get("turn5_query", "")
            if qid and t5:
                _turn5_lookup[qid] = t5

    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            qid = row["query_id"]
            eid = row["eval_id"]

            # Parse conversation_history JSON (empty for single-turn rows)
            ch = row.get("conversation_history", "")
            row["conversation_history"] = json.loads(ch) if ch and ch.strip() else []

            # Normalise boolean string
            row["is_ambiguous"] = row.get("is_ambiguous", "false").lower() == "true"

            if qid not in _query_store:
                _query_store[qid] = []
                _query_order.append(qid)
            _query_store[qid].append(row)
            _eval_store[eid] = row


def get_eval_by_id(eval_id: str) -> Optional[dict]:
    return _eval_store.get(eval_id)


def get_query_rows(query_id: str) -> Optional[List[dict]]:
    return _query_store.get(query_id)


def get_query_order() -> List[str]:
    return _query_order


def get_all_eval_ids() -> List[str]:
    return list(_eval_store.keys())


def get_turn5_query(query_id: str) -> str:
    return _turn5_lookup.get(query_id, "")


def get_blinding_mapping() -> dict:
    with open(BLINDING_PATH, encoding="utf-8") as f:
        return json.load(f)
