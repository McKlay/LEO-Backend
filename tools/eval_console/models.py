from pydantic import BaseModel, Field
from typing import Optional


class LoginRequest(BaseModel):
    reviewer_id: str
    password: str


class RatingIn(BaseModel):
    eval_id: str
    reviewer_id: str
    legal_accuracy: Optional[int] = Field(None, ge=1, le=4)
    hallucination: Optional[str] = None
    citation_notes: Optional[str] = None
    clarification_score: Optional[int] = Field(None, ge=1, le=4)
    notes: Optional[str] = None
    turn6_legal_accuracy: Optional[int] = Field(None, ge=1, le=4)
    turn6_hallucination: Optional[str] = None
    turn6_citation_notes: Optional[str] = None
    turn6_notes: Optional[str] = None
    flagged: int = 0

    model_config = {"extra": "ignore"}
