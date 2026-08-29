import hashlib
import hmac
import os
from typing import Optional

from fastapi import Header, HTTPException

_SECRET = os.getenv("SECRET_KEY", "dev_secret_insecure_change_in_prod")

_REVIEWER_PASSWORDS: dict[str, str] = {
    "reviewer_1": os.getenv("REVIEWER_1_PASSWORD", ""),
    "reviewer_2": os.getenv("REVIEWER_2_PASSWORD", ""),
}


def _sign(value: str) -> str:
    return hmac.new(
        _SECRET.encode(), value.encode(), hashlib.sha256
    ).hexdigest()[:20]


def make_token(reviewer_id: str) -> str:
    return f"{reviewer_id}:{_sign(reviewer_id)}"


def verify_token(token: str) -> Optional[str]:
    if not token or ":" not in token:
        return None
    reviewer_id, _, sig = token.partition(":")
    if reviewer_id not in _REVIEWER_PASSWORDS:
        return None
    if hmac.compare_digest(_sign(reviewer_id), sig):
        return reviewer_id
    return None


def check_reviewer_password(reviewer_id: str, password: str) -> bool:
    expected = _REVIEWER_PASSWORDS.get(reviewer_id, "")
    if not expected or not password:
        return False
    return hmac.compare_digest(expected, password)


def check_admin_password(password: str) -> bool:
    admin_pwd = os.getenv("ADMIN_PASSWORD", "")
    if not admin_pwd or not password:
        return False
    return hmac.compare_digest(admin_pwd, password)


async def get_current_reviewer(
    authorization: Optional[str] = Header(None),
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    token = authorization[7:]
    reviewer_id = verify_token(token)
    if not reviewer_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return reviewer_id
