"""Integration tests for the LEO Expert Evaluation Console.

Covers every route group: auth, queries, ratings, progress, export, and
the three static HTML pages.  External Supabase calls are mocked; the
knowledge-base CSV and blinding-map files are loaded from disk (they
exist in the repo and have no side effects).

Run from the repo root:
    python -m pytest tools/eval_console/tests/ -v

Or from the eval_console directory:
    python -m pytest tests/ -v
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ── Supabase mock factory ─────────────────────────────────────────────────────


def _mock_db(data: list | None = None, count: int | None = None) -> MagicMock:
    """Return a fully-chainable Supabase client mock.

    Every fluent method (select, eq, filter, …) returns the same chain so
    callers can add as many filters as they like. `.execute()` returns a
    result with ``.data`` and ``.count`` set to the supplied values.
    """
    result = MagicMock()
    result.data = list(data) if data is not None else []
    result.count = count if count is not None else len(result.data)

    chain = MagicMock()
    for method in ("select", "eq", "filter", "limit", "upsert", "delete"):
        getattr(chain, method).return_value = chain
    chain.execute.return_value = result

    client = MagicMock()
    client.table.return_value = chain
    return client


# ── Module-scoped app fixture ─────────────────────────────────────────────────


@pytest.fixture(scope="module")
def app_client():
    """Spin up one TestClient for the whole module.

    The Supabase ``get_client`` references in each route module are
    patched to return an empty-data mock.  All other code (data loader,
    blinding logic, auth, etc.) runs with real logic against real files.
    """
    empty_db = _mock_db()
    patches = [
        patch("routes.queries.get_client", return_value=empty_db),
        patch("routes.ratings.get_client", return_value=empty_db),
        patch("routes.progress.get_client", return_value=empty_db),
        patch("routes.export.get_client", return_value=empty_db),
    ]
    for p in patches:
        p.start()
    try:
        from main import app  # imported here so conftest env vars are already set
        with TestClient(app) as tc:
            yield tc
    finally:
        for p in patches:
            p.stop()


# ── Auth helpers ──────────────────────────────────────────────────────────────


def _login(client: TestClient, reviewer_id: str, password: str) -> str:
    """Return a ready-to-use ``Authorization: Bearer …`` header value."""
    r = client.post("/auth/login", json={"reviewer_id": reviewer_id, "password": password})
    assert r.status_code == 200, f"Login unexpectedly failed: {r.text}"
    return f"Bearer {r.json()['token']}"


def _r1(client: TestClient) -> str:
    return _login(client, "reviewer_1", "int_test_r1_pass")


def _r2(client: TestClient) -> str:
    return _login(client, "reviewer_2", "int_test_r2_pass")


# ── Data helpers (populated after lifespan runs load_data) ────────────────────


def _first_eval_id() -> str:
    from data.loader import get_all_eval_ids

    ids = get_all_eval_ids()
    assert ids, "No eval IDs loaded — is the CSV missing?"
    return ids[0]


def _first_query_id() -> str:
    from data.loader import get_query_order

    order = get_query_order()
    assert order, "No queries loaded — is the CSV missing?"
    return order[0]


# ═════════════════════════════════════════════════════════════════════════════
# Auth
# ═════════════════════════════════════════════════════════════════════════════


class TestAuth:
    def test_reviewer_1_login_returns_token(self, app_client):
        r = app_client.post(
            "/auth/login",
            json={"reviewer_id": "reviewer_1", "password": "int_test_r1_pass"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "token" in body
        assert body["reviewer_id"] == "reviewer_1"
        assert body["token"].startswith("reviewer_1:")

    def test_reviewer_2_login_returns_token(self, app_client):
        r = app_client.post(
            "/auth/login",
            json={"reviewer_id": "reviewer_2", "password": "int_test_r2_pass"},
        )
        assert r.status_code == 200
        assert r.json()["reviewer_id"] == "reviewer_2"

    def test_wrong_password_is_401(self, app_client):
        r = app_client.post(
            "/auth/login",
            json={"reviewer_id": "reviewer_1", "password": "completely_wrong"},
        )
        assert r.status_code == 401

    def test_unknown_reviewer_is_401(self, app_client):
        r = app_client.post(
            "/auth/login",
            json={"reviewer_id": "reviewer_99", "password": "anypass"},
        )
        assert r.status_code == 401

    def test_empty_password_is_401(self, app_client):
        r = app_client.post(
            "/auth/login",
            json={"reviewer_id": "reviewer_1", "password": ""},
        )
        assert r.status_code == 401

    def test_token_is_deterministic(self, app_client):
        """Same credentials must always produce the same HMAC-signed token."""
        t1 = _login(app_client, "reviewer_1", "int_test_r1_pass")
        t2 = _login(app_client, "reviewer_1", "int_test_r1_pass")
        assert t1 == t2


# ═════════════════════════════════════════════════════════════════════════════
# Queries
# ═════════════════════════════════════════════════════════════════════════════


class TestQueries:
    def test_list_requires_auth(self, app_client):
        assert app_client.get("/api/queries").status_code == 401

    def test_list_with_tampered_token_is_401(self, app_client):
        r = app_client.get(
            "/api/queries",
            headers={"Authorization": "Bearer reviewer_1:000000000000000000"},
        )
        assert r.status_code == 401

    def test_list_returns_non_empty_list(self, app_client):
        r = app_client.get("/api/queries", headers={"Authorization": _r1(app_client)})
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) > 0

    def test_list_item_has_required_fields(self, app_client):
        r = app_client.get("/api/queries", headers={"Authorization": _r1(app_client)})
        item = r.json()[0]
        required = {
            "query_id", "position", "query_text", "language",
            "eval_ids", "rated_count", "total_answers", "is_flagged", "has_turn6",
        }
        assert required.issubset(item.keys())

    def test_list_item_has_three_configs(self, app_client):
        """Every query must have exactly 3 eval_ids (Q, M, J configs)."""
        r = app_client.get("/api/queries", headers={"Authorization": _r1(app_client)})
        for item in r.json():
            assert item["total_answers"] == 3, f"Expected 3 configs for {item['query_id']}"

    def test_list_shows_zero_rated_when_db_empty(self, app_client):
        r = app_client.get("/api/queries", headers={"Authorization": _r1(app_client)})
        for item in r.json():
            assert item["rated_count"] == 0
            assert item["is_flagged"] is False

    def test_list_position_is_sequential(self, app_client):
        r = app_client.get("/api/queries", headers={"Authorization": _r1(app_client)})
        positions = [item["position"] for item in r.json()]
        assert positions == list(range(1, len(positions) + 1))

    def test_get_detail_returns_200(self, app_client):
        auth = _r1(app_client)
        qid = _first_query_id()
        r = app_client.get(f"/api/queries/{qid}", headers={"Authorization": auth})
        assert r.status_code == 200

    def test_get_detail_has_required_fields(self, app_client):
        auth = _r1(app_client)
        body = app_client.get(
            f"/api/queries/{_first_query_id()}", headers={"Authorization": auth}
        ).json()
        required = {
            "query_id", "position", "total", "query_text", "language",
            "answers", "reference_answer", "gold_article_refs", "has_any_turn6",
        }
        assert required.issubset(body.keys())

    def test_get_detail_answers_are_blinded(self, app_client):
        """System labels must be System A/B/C — raw config labels must not leak."""
        auth = _r1(app_client)
        answers = app_client.get(
            f"/api/queries/{_first_query_id()}", headers={"Authorization": auth}
        ).json()["answers"]
        labels = {a["system_label"] for a in answers}
        assert labels == {"System A", "System B", "System C"}
        for a in answers:
            assert a["system_label"] not in ("Q", "M", "J")

    def test_get_detail_has_three_answers(self, app_client):
        auth = _r1(app_client)
        body = app_client.get(
            f"/api/queries/{_first_query_id()}", headers={"Authorization": auth}
        ).json()
        assert len(body["answers"]) == 3

    def test_get_nonexistent_query_is_404(self, app_client):
        auth = _r1(app_client)
        assert (
            app_client.get("/api/queries/NOTEXIST_XYZ99", headers={"Authorization": auth}).status_code
            == 404
        )


# ═════════════════════════════════════════════════════════════════════════════
# Ratings
# ═════════════════════════════════════════════════════════════════════════════


class TestRatings:
    def test_post_requires_auth(self, app_client):
        payload = {"eval_id": _first_eval_id(), "reviewer_id": "reviewer_1", "flagged": 0}
        assert app_client.post("/api/ratings", json=payload).status_code == 401

    def test_post_valid_full_rating_returns_saved(self, app_client):
        auth = _r1(app_client)
        payload = {
            "eval_id": _first_eval_id(),
            "reviewer_id": "reviewer_1",
            "legal_accuracy": 3,
            "hallucination": "none",
            "citation_notes": "Citations accurate",
            "clarification_score": 2,
            "notes": "Good answer",
            "flagged": 0,
        }
        r = app_client.post("/api/ratings", json=payload, headers={"Authorization": auth})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "saved"
        assert "saved_at" in body

    def test_post_flag_only_no_scores_is_valid(self, app_client):
        """Saving with only flagged=1 and no numeric scores must succeed."""
        auth = _r1(app_client)
        payload = {"eval_id": _first_eval_id(), "reviewer_id": "reviewer_1", "flagged": 1}
        r = app_client.post("/api/ratings", json=payload, headers={"Authorization": auth})
        assert r.status_code == 200

    def test_post_cross_reviewer_is_403(self, app_client):
        """reviewer_1 token must not be able to save ratings as reviewer_2."""
        auth = _r1(app_client)
        payload = {"eval_id": _first_eval_id(), "reviewer_id": "reviewer_2", "flagged": 0}
        assert app_client.post("/api/ratings", json=payload, headers={"Authorization": auth}).status_code == 403

    def test_post_unknown_eval_id_is_404(self, app_client):
        auth = _r1(app_client)
        payload = {"eval_id": "FAKE-EVAL-ID-9999", "reviewer_id": "reviewer_1", "flagged": 0}
        assert app_client.post("/api/ratings", json=payload, headers={"Authorization": auth}).status_code == 404

    def test_post_legal_accuracy_above_max_is_422(self, app_client):
        """legal_accuracy=5 exceeds the 1-4 range and must be rejected."""
        auth = _r1(app_client)
        payload = {
            "eval_id": _first_eval_id(),
            "reviewer_id": "reviewer_1",
            "legal_accuracy": 5,
            "flagged": 0,
        }
        assert app_client.post("/api/ratings", json=payload, headers={"Authorization": auth}).status_code == 422

    def test_post_legal_accuracy_below_min_is_422(self, app_client):
        auth = _r1(app_client)
        payload = {
            "eval_id": _first_eval_id(),
            "reviewer_id": "reviewer_1",
            "legal_accuracy": 0,
            "flagged": 0,
        }
        assert app_client.post("/api/ratings", json=payload, headers={"Authorization": auth}).status_code == 422

    def test_post_clarification_score_out_of_range_is_422(self, app_client):
        auth = _r1(app_client)
        payload = {
            "eval_id": _first_eval_id(),
            "reviewer_id": "reviewer_1",
            "clarification_score": 10,
            "flagged": 0,
        }
        assert app_client.post("/api/ratings", json=payload, headers={"Authorization": auth}).status_code == 422

    def test_get_own_ratings_returns_list(self, app_client):
        auth = _r1(app_client)
        r = app_client.get("/api/ratings/reviewer_1", headers={"Authorization": auth})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_cross_reviewer_is_403(self, app_client):
        auth = _r1(app_client)
        assert app_client.get("/api/ratings/reviewer_2", headers={"Authorization": auth}).status_code == 403

    def test_get_requires_auth(self, app_client):
        assert app_client.get("/api/ratings/reviewer_1").status_code == 401


# ═════════════════════════════════════════════════════════════════════════════
# Progress
# ═════════════════════════════════════════════════════════════════════════════


class TestProgress:
    def test_my_progress_requires_auth(self, app_client):
        assert app_client.get("/api/progress").status_code == 401

    def test_my_progress_structure(self, app_client):
        r = app_client.get("/api/progress", headers={"Authorization": _r1(app_client)})
        assert r.status_code == 200
        body = r.json()
        assert body["reviewer_id"] == "reviewer_1"
        assert "completed" in body and "total" in body and "percent" in body

    def test_my_progress_zero_completed_against_empty_db(self, app_client):
        r = app_client.get("/api/progress", headers={"Authorization": _r1(app_client)})
        body = r.json()
        assert body["completed"] == 0
        assert body["percent"] == 0.0
        assert body["total"] > 0  # real CSV was loaded

    def test_admin_progress_valid_password(self, app_client):
        r = app_client.get(
            "/api/progress/admin",
            headers={"X-Admin-Password": "int_test_admin_pass"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "total" in body
        assert "reviewer_1" in body and "reviewer_2" in body

    def test_admin_progress_reviewer_totals_match(self, app_client):
        r = app_client.get(
            "/api/progress/admin",
            headers={"X-Admin-Password": "int_test_admin_pass"},
        )
        body = r.json()
        assert body["reviewer_1"]["total"] == body["total"]
        assert body["reviewer_2"]["total"] == body["total"]

    def test_admin_progress_wrong_password_is_403(self, app_client):
        assert (
            app_client.get(
                "/api/progress/admin", headers={"X-Admin-Password": "wrongpass"}
            ).status_code
            == 403
        )

    def test_admin_progress_no_password_is_403(self, app_client):
        assert app_client.get("/api/progress/admin").status_code == 403


# ═════════════════════════════════════════════════════════════════════════════
# Export
# ═════════════════════════════════════════════════════════════════════════════


class TestExport:
    def test_csv_requires_admin_auth(self, app_client):
        assert app_client.get("/api/export/csv").status_code == 403

    def test_csv_wrong_password_is_403(self, app_client):
        assert (
            app_client.get(
                "/api/export/csv", headers={"X-Admin-Password": "wrong"}
            ).status_code
            == 403
        )

    def test_csv_returns_200_with_correct_password(self, app_client):
        r = app_client.get(
            "/api/export/csv",
            headers={"X-Admin-Password": "int_test_admin_pass"},
        )
        assert r.status_code == 200

    def test_csv_content_type(self, app_client):
        r = app_client.get(
            "/api/export/csv",
            headers={"X-Admin-Password": "int_test_admin_pass"},
        )
        assert "text/csv" in r.headers.get("content-type", "")

    def test_csv_contains_header_row(self, app_client):
        r = app_client.get(
            "/api/export/csv",
            headers={"X-Admin-Password": "int_test_admin_pass"},
        )
        assert "eval_id" in r.text
        assert "query_id" in r.text
        assert "reviewer_1_legal_accuracy" in r.text

    def test_csv_contains_data_rows(self, app_client):
        r = app_client.get(
            "/api/export/csv",
            headers={"X-Admin-Password": "int_test_admin_pass"},
        )
        rows = [ln for ln in r.text.splitlines() if ln.strip()]
        assert len(rows) > 1, "Expected header + at least one data row"

    def test_csv_content_disposition_attachment(self, app_client):
        r = app_client.get(
            "/api/export/csv",
            headers={"X-Admin-Password": "int_test_admin_pass"},
        )
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert ".csv" in cd


# ═════════════════════════════════════════════════════════════════════════════
# Frontend pages
# ═════════════════════════════════════════════════════════════════════════════


class TestFrontendPages:
    def test_index_returns_html(self, app_client):
        r = app_client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_review_returns_html(self, app_client):
        r = app_client.get("/review")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_progress_page_returns_html(self, app_client):
        r = app_client.get("/progress")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_openapi_docs_available(self, app_client):
        r = app_client.get("/docs")
        assert r.status_code == 200
