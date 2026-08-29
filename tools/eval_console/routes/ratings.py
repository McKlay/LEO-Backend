from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_reviewer
from data.loader import get_eval_by_id
from db import get_conn
from models import RatingIn

router = APIRouter(prefix="/api/ratings")


@router.post("")
def upsert_rating(rating: RatingIn, reviewer_id: str = Depends(get_current_reviewer)):
    if rating.reviewer_id != reviewer_id:
        raise HTTPException(status_code=403, detail="Cannot save ratings for another reviewer")

    if not get_eval_by_id(rating.eval_id):
        raise HTTPException(status_code=404, detail="eval_id not found")

    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO ratings
                   (eval_id, reviewer_id, legal_accuracy, hallucination,
                    citation_notes, clarification_score, notes,
                    turn6_legal_accuracy, turn6_hallucination,
                    turn6_citation_notes, turn6_notes, flagged, saved_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(eval_id, reviewer_id) DO UPDATE SET
                   legal_accuracy       = excluded.legal_accuracy,
                   hallucination        = excluded.hallucination,
                   citation_notes       = excluded.citation_notes,
                   clarification_score  = excluded.clarification_score,
                   notes                = excluded.notes,
                   turn6_legal_accuracy = excluded.turn6_legal_accuracy,
                   turn6_hallucination  = excluded.turn6_hallucination,
                   turn6_citation_notes = excluded.turn6_citation_notes,
                   turn6_notes          = excluded.turn6_notes,
                   flagged              = excluded.flagged,
                   saved_at             = excluded.saved_at""",
            (
                rating.eval_id, rating.reviewer_id,
                rating.legal_accuracy, rating.hallucination,
                rating.citation_notes, rating.clarification_score, rating.notes,
                rating.turn6_legal_accuracy, rating.turn6_hallucination,
                rating.turn6_citation_notes, rating.turn6_notes,
                rating.flagged, now,
            ),
        )
    return {"status": "saved", "saved_at": now}


@router.get("/{target_reviewer_id}")
def get_reviewer_ratings(
    target_reviewer_id: str,
    reviewer_id: str = Depends(get_current_reviewer),
):
    if target_reviewer_id != reviewer_id:
        raise HTTPException(status_code=403, detail="Cannot view another reviewer's ratings")

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM ratings WHERE reviewer_id = ?", (reviewer_id,)
        ).fetchall()

    return [dict(r) for r in rows]
