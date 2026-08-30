from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_reviewer
from data.loader import get_eval_by_id
from db import get_client
from models import RatingIn

router = APIRouter(prefix="/api/ratings")


@router.post("")
def upsert_rating(rating: RatingIn, reviewer_id: str = Depends(get_current_reviewer)):
    if rating.reviewer_id != reviewer_id:
        raise HTTPException(status_code=403, detail="Cannot save ratings for another reviewer")

    if not get_eval_by_id(rating.eval_id):
        raise HTTPException(status_code=404, detail="eval_id not found")

    now = datetime.now(timezone.utc).isoformat()
    get_client().table("ratings").upsert(
        {
            "eval_id": rating.eval_id,
            "reviewer_id": rating.reviewer_id,
            "legal_accuracy": rating.legal_accuracy,
            "hallucination": rating.hallucination,
            "citation_notes": rating.citation_notes,
            "clarification_score": rating.clarification_score,
            "notes": rating.notes,
            "turn6_legal_accuracy": rating.turn6_legal_accuracy,
            "turn6_hallucination": rating.turn6_hallucination,
            "turn6_citation_notes": rating.turn6_citation_notes,
            "turn6_notes": rating.turn6_notes,
            "flagged": rating.flagged,
            "saved_at": now,
        },
        on_conflict="eval_id,reviewer_id",
    ).execute()
    return {"status": "saved", "saved_at": now}


@router.get("/{target_reviewer_id}")
def get_reviewer_ratings(
    target_reviewer_id: str,
    reviewer_id: str = Depends(get_current_reviewer),
):
    if target_reviewer_id != reviewer_id:
        raise HTTPException(status_code=403, detail="Cannot view another reviewer's ratings")

    result = get_client().table("ratings").select("*").eq("reviewer_id", reviewer_id).execute()
    return result.data
