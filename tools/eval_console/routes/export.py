import csv
import io
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse

from auth import check_admin_password
from data.blinding import config_to_system_map
from data.loader import get_blinding_mapping, get_query_order, get_query_rows
from db import get_client

try:
    from sklearn.metrics import cohen_kappa_score
    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False

router = APIRouter(prefix="/api/export")

_FIELDNAMES = [
    "eval_id", "query_id", "query_text", "language", "query_type", "is_ambiguous",
    "topic", "config_label", "variant", "system_label",
    "system_answer", "reference_answer", "gold_article_refs",
    "system_answer_turn6", "turn6_reference_answer",
    "reviewer_1_legal_accuracy", "reviewer_1_hallucination",
    "reviewer_1_citation_notes", "reviewer_1_clarification_score",
    "reviewer_1_notes", "reviewer_1_turn6_legal_accuracy",
    "reviewer_1_turn6_hallucination", "reviewer_1_turn6_citation_notes",
    "reviewer_1_turn6_notes", "reviewer_1_flagged",
    "reviewer_2_legal_accuracy", "reviewer_2_hallucination",
    "reviewer_2_citation_notes", "reviewer_2_clarification_score",
    "reviewer_2_notes", "reviewer_2_turn6_legal_accuracy",
    "reviewer_2_turn6_hallucination", "reviewer_2_turn6_citation_notes",
    "reviewer_2_turn6_notes", "reviewer_2_flagged",
    "mean_legal_accuracy",
]


@router.get("/csv")
def export_csv(
    x_admin_password: Optional[str] = Header(None, alias="X-Admin-Password"),
):
    if not check_admin_password(x_admin_password or ""):
        raise HTTPException(status_code=403, detail="Invalid admin password")

    client = get_client()
    r1 = {r["eval_id"]: r for r in client.table("ratings").select("*").eq("reviewer_id", "reviewer_1").execute().data}
    r2 = {r["eval_id"]: r for r in client.table("ratings").select("*").eq("reviewer_id", "reviewer_2").execute().data}

    blinding = get_blinding_mapping()
    label_to_variant: dict = blinding.get("label_to_variant", {})

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=_FIELDNAMES, extrasaction="ignore")
    writer.writeheader()

    # Per-config arrays for Cohen's kappa
    kappa_data: dict[str, tuple[list, list]] = {
        "Q": ([], []), "M": ([], []), "J": ([], [])
    }

    for qid in get_query_order():
        rows = get_query_rows(qid)
        mapping = config_to_system_map(qid)
        for row in rows:
            eid = row["eval_id"]
            config = row["config_label"]
            r1r = r1.get(eid, {})
            r2r = r2.get(eid, {})

            la1 = r1r.get("legal_accuracy")
            la2 = r2r.get("legal_accuracy")
            if la1 is not None and la2 is not None:
                kappa_data[config][0].append(int(la1))
                kappa_data[config][1].append(int(la2))

            mean_la = (la1 + la2) / 2 if la1 is not None and la2 is not None else None

            writer.writerow({
                "eval_id": eid,
                "query_id": qid,
                "query_text": row["query_text"],
                "language": row["language"],
                "query_type": row["query_type"],
                "is_ambiguous": row["is_ambiguous"],
                "topic": row["topic"],
                "config_label": config,
                "variant": label_to_variant.get(config, ""),
                "system_label": mapping.get(config, ""),
                "system_answer": row["system_answer"],
                "reference_answer": row["reference_answer"],
                "gold_article_refs": row["gold_article_refs"],
                "system_answer_turn6": row.get("system_answer_turn6", ""),
                "turn6_reference_answer": row.get("turn6_reference_answer", ""),
                "reviewer_1_legal_accuracy": r1r.get("legal_accuracy"),
                "reviewer_1_hallucination": r1r.get("hallucination"),
                "reviewer_1_citation_notes": r1r.get("citation_notes"),
                "reviewer_1_clarification_score": r1r.get("clarification_score"),
                "reviewer_1_notes": r1r.get("notes"),
                "reviewer_1_turn6_legal_accuracy": r1r.get("turn6_legal_accuracy"),
                "reviewer_1_turn6_hallucination": r1r.get("turn6_hallucination"),
                "reviewer_1_turn6_citation_notes": r1r.get("turn6_citation_notes"),
                "reviewer_1_turn6_notes": r1r.get("turn6_notes"),
                "reviewer_1_flagged": r1r.get("flagged"),
                "reviewer_2_legal_accuracy": r2r.get("legal_accuracy"),
                "reviewer_2_hallucination": r2r.get("hallucination"),
                "reviewer_2_citation_notes": r2r.get("citation_notes"),
                "reviewer_2_clarification_score": r2r.get("clarification_score"),
                "reviewer_2_notes": r2r.get("notes"),
                "reviewer_2_turn6_legal_accuracy": r2r.get("turn6_legal_accuracy"),
                "reviewer_2_turn6_hallucination": r2r.get("turn6_hallucination"),
                "reviewer_2_turn6_citation_notes": r2r.get("turn6_citation_notes"),
                "reviewer_2_turn6_notes": r2r.get("turn6_notes"),
                "reviewer_2_flagged": r2r.get("flagged"),
                "mean_legal_accuracy": mean_la,
            })

    # Append Cohen's kappa summary rows
    if _HAS_SKLEARN:
        blinding_map = get_blinding_mapping()
        l2v = blinding_map.get("label_to_variant", {})
        for config_label, (y1, y2) in kappa_data.items():
            if len(y1) >= 2:
                kappa = cohen_kappa_score(y1, y2, weights="quadratic")
                variant = l2v.get(config_label, config_label)
                writer.writerow({
                    "eval_id": f"KAPPA_{config_label}",
                    "query_id": f"cohen_kappa_{variant}",
                    "mean_legal_accuracy": round(kappa, 4),
                })

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=merged_ratings.csv"},
    )
