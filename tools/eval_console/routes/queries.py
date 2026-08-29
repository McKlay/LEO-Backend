from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_reviewer
from data.blinding import config_to_system_map, get_display_order
from data.loader import get_query_order, get_query_rows, get_turn5_query
from db import get_conn

router = APIRouter(prefix="/api/queries")


def _rated_eval_ids(reviewer_id: str) -> set[str]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT eval_id FROM ratings
               WHERE reviewer_id = ?
                 AND legal_accuracy IS NOT NULL
                 AND hallucination IS NOT NULL""",
            (reviewer_id,),
        ).fetchall()
    return {r["eval_id"] for r in rows}


def _flagged_eval_ids(reviewer_id: str) -> set[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT eval_id FROM ratings WHERE reviewer_id = ? AND flagged = 1",
            (reviewer_id,),
        ).fetchall()
    return {r["eval_id"] for r in rows}


@router.get("")
def list_queries(reviewer_id: str = Depends(get_current_reviewer)):
    rated = _rated_eval_ids(reviewer_id)
    flagged = _flagged_eval_ids(reviewer_id)
    order = get_query_order()
    result = []
    for i, qid in enumerate(order):
        rows = get_query_rows(qid)
        ref = rows[0]
        eval_ids = [r["eval_id"] for r in rows]
        rated_count = sum(1 for eid in eval_ids if eid in rated)
        is_flagged = any(eid in flagged for eid in eval_ids)
        has_turn6 = any(r.get("system_answer_turn6", "").strip() for r in rows)
        result.append({
            "query_id": qid,
            "position": i + 1,
            "query_text": ref["query_text"],
            "language": ref["language"],
            "query_type": ref["query_type"],
            "is_ambiguous": ref["is_ambiguous"],
            "topic": ref["topic"],
            "eval_ids": eval_ids,   # opaque identifiers — no config info leaked
            "rated_count": rated_count,
            "total_answers": len(eval_ids),
            "is_flagged": is_flagged,
            "has_turn6": has_turn6,
        })
    return result


@router.get("/{query_id}")
def get_query(query_id: str, reviewer_id: str = Depends(get_current_reviewer)):
    rows = get_query_rows(query_id)
    if not rows:
        raise HTTPException(status_code=404, detail="Query not found")

    order = get_query_order()
    try:
        pos = order.index(query_id) + 1
    except ValueError:
        pos = 0

    mapping = config_to_system_map(query_id)        # {config_label: "System X"}
    display_order = get_display_order(query_id)     # shuffled config labels
    config_rows = {r["config_label"]: r for r in rows}

    ref = rows[0]

    answers = []
    for config_label in display_order:
        row = config_rows.get(config_label)
        if not row:
            continue
        t6 = row.get("system_answer_turn6", "").strip()
        answers.append({
            "eval_id": row["eval_id"],
            "system_label": mapping[config_label],
            "answer": row["system_answer"],
            "has_turn6": bool(t6),
            "turn6_answer": t6,
        })

    has_any_turn6 = any(a["has_turn6"] for a in answers)

    return {
        "query_id": query_id,
        "position": pos,
        "total": len(order),
        "query_text": ref["query_text"],
        "language": ref["language"],
        "query_type": ref["query_type"],
        "is_ambiguous": ref["is_ambiguous"],
        "topic": ref["topic"],
        "conversation_history": ref["conversation_history"],
        "reference_answer": ref["reference_answer"],
        "gold_article_refs": ref["gold_article_refs"],
        "has_any_turn6": has_any_turn6,
        "turn5_query": get_turn5_query(query_id),
        "turn6_reference_answer": ref.get("turn6_reference_answer", ""),
        "answers": answers,
        "prev_query_id": order[pos - 2] if pos > 1 else None,
        "next_query_id": order[pos] if pos < len(order) else None,
    }
