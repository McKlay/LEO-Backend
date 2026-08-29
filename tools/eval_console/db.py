import os
import sqlite3
from pathlib import Path


def _db_path() -> Path:
    p = Path(os.getenv("DATABASE_PATH", "data/ratings.db"))
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ratings (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                eval_id                 TEXT NOT NULL,
                reviewer_id             TEXT NOT NULL,
                legal_accuracy          INTEGER,
                hallucination           TEXT,
                citation_notes          TEXT,
                clarification_score     INTEGER,
                notes                   TEXT,
                turn6_legal_accuracy    INTEGER,
                turn6_hallucination     TEXT,
                turn6_citation_notes    TEXT,
                turn6_notes             TEXT,
                flagged                 INTEGER DEFAULT 0,
                saved_at                TEXT,
                UNIQUE(eval_id, reviewer_id)
            )
        """)
