from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header

from auth import check_admin_password, get_current_reviewer
from data.loader import get_all_eval_ids
from db import get_client

router = APIRouter(prefix="/api/progress")


def _count_completed(reviewer_id: str) -> int:
    result = (
        get_client()
        .table("ratings")
        .select("*", count="exact")
        .eq("reviewer_id", reviewer_id)
        .filter("legal_accuracy", "not.is", "null")
        .filter("hallucination", "not.is", "null")
        .execute()
    )
    return result.count or 0


@router.get("")
def my_progress(reviewer_id: str = Depends(get_current_reviewer)):
    total = len(get_all_eval_ids())
    completed = _count_completed(reviewer_id)
    return {
        "reviewer_id": reviewer_id,
        "completed": completed,
        "total": total,
        "percent": round(completed / total * 100, 1) if total else 0,
    }


@router.get("/admin")
def admin_progress(
    x_admin_password: Optional[str] = Header(None, alias="X-Admin-Password"),
):
    if not check_admin_password(x_admin_password or ""):
        raise HTTPException(status_code=403, detail="Invalid admin password")

    total = len(get_all_eval_ids())
    return {
        "total": total,
        "reviewer_1": {"completed": _count_completed("reviewer_1"), "total": total},
        "reviewer_2": {"completed": _count_completed("reviewer_2"), "total": total},
    }
