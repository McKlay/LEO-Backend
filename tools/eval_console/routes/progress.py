from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header

from auth import check_admin_password, get_current_reviewer
from data.loader import get_all_eval_ids
from db import get_conn

router = APIRouter(prefix="/api/progress")


def _count_completed(reviewer_id: str) -> int:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT COUNT(*) FROM ratings
               WHERE reviewer_id = ?
                 AND legal_accuracy IS NOT NULL
                 AND hallucination IS NOT NULL""",
            (reviewer_id,),
        ).fetchone()
    return row[0]


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
