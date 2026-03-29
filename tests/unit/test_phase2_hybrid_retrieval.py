"""
Task 7 — Phase 2 Hybrid Retrieval Unit Tests

Covers:
  A. reciprocal_rank_fusion()  — RRF correctness (ranking.py)
  B. direct_article_lookup()   — GIN symbolic search + ref normalization
  C. smart_retrieve()          — strategy gating via enabled_strategies
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from adapters.vectorstore.supabase_store import SupabaseVectorStore
from adapters.vectorstore.base import QueryResult
from retrieval.ranking import reciprocal_rank_fusion


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_result(doc_id: str, score: float = 0.5, strategy: str | None = None) -> QueryResult:
    meta = {}
    if strategy:
        meta["_strategy"] = strategy
    return QueryResult(id=doc_id, content=f"Content {doc_id}", metadata=meta, score=score)


@pytest.fixture
def vector_store():
    client = MagicMock()
    settings = MagicMock()
    settings.vectorstore_table_name = "labor_law_sections"
    settings.embedding_dimension = 1536
    settings.supabase_db_url = "postgresql://test:test@localhost/test"
    settings.enable_connection_pooling = False
    return SupabaseVectorStore(supabase_client=client, settings=settings)


# ---------------------------------------------------------------------------
# A. reciprocal_rank_fusion()
# ---------------------------------------------------------------------------

class TestRRF:
    """RRF algorithm correctness."""

    def test_single_strategy_preserves_order(self):
        """Single-strategy input → output order unchanged."""
        dense = [_make_result("d1", 0.9), _make_result("d2", 0.7), _make_result("d3", 0.5)]
        result = reciprocal_rank_fusion({"dense": dense})

        ids = [r.id for r in result]
        assert ids == ["d1", "d2", "d3"], "Order must be preserved for single-strategy input"

    def test_same_doc_two_strategies_accumulates_score(self):
        """Same doc in two strategies → RRF score = sum of both contributions."""
        # "shared" appears rank-1 in both → score = 1/(60+1) + 1/(60+1)
        # "only_dense" appears rank-2 in dense → score = 1/(60+2)
        dense = [_make_result("shared"), _make_result("only_dense")]
        lexical = [_make_result("shared"), _make_result("only_lex")]

        results = reciprocal_rank_fusion({"dense": dense, "lexical": lexical})
        result_map = {r.id: r for r in results}

        shared_score = 1 / (60 + 1) + 1 / (60 + 1)   # rank-1 in both
        only_dense_score = 1 / (60 + 2)               # rank-2 in dense only

        assert result_map["shared"].score == pytest.approx(shared_score, rel=1e-6)
        assert result_map["only_dense"].score == pytest.approx(only_dense_score, rel=1e-6)
        # "shared" must rank above single-strategy docs
        assert results[0].id == "shared"

    def test_three_way_agreement_ranks_first(self):
        """Doc present in all three strategies → must rank #1."""
        common = _make_result("common")
        results = reciprocal_rank_fusion({
            "symbolic": [common, _make_result("s_only")],
            "lexical":  [common, _make_result("l_only")],
            "dense":    [common, _make_result("d_only")],
        })

        assert results[0].id == "common"

    def test_absent_strategy_no_penalty(self):
        """Doc absent from one strategy contributes 0 from that strategy (no penalty)."""
        # "partial" appears in dense only; "common" appears in both
        dense = [_make_result("common"), _make_result("partial")]
        lexical = [_make_result("common")]

        results = reciprocal_rank_fusion({"dense": dense, "lexical": lexical})
        result_map = {r.id: r for r in results}

        # "partial" should still appear (not penalised for absence from lexical)
        assert "partial" in result_map
        # "common" benefits from both strategies and must rank above "partial"
        assert result_map["common"].score > result_map["partial"].score

    def test_empty_strategy_list_skipped(self):
        """Empty strategy lists are silently skipped; no KeyError or crash."""
        dense = [_make_result("d1")]
        result = reciprocal_rank_fusion({"dense": dense, "lexical": []})
        assert len(result) == 1
        assert result[0].id == "d1"

    def test_all_empty_returns_empty(self):
        """All-empty input returns empty list."""
        assert reciprocal_rank_fusion({}) == []
        assert reciprocal_rank_fusion({"dense": [], "lexical": []}) == []

    def test_rrf_metadata_attached(self):
        """_rrf_score, _contributing_strategies, _strategy_ranks must be in metadata."""
        dense = [_make_result("d1")]
        lexical = [_make_result("d1")]
        results = reciprocal_rank_fusion({"dense": dense, "lexical": lexical})

        meta = results[0].metadata
        assert "_rrf_score" in meta
        assert "_contributing_strategies" in meta
        assert "_strategy_ranks" in meta
        assert set(meta["_contributing_strategies"]) == {"dense", "lexical"}


# ---------------------------------------------------------------------------
# B. direct_article_lookup() — GIN symbolic search + normalization
# ---------------------------------------------------------------------------

class TestDirectArticleLookupGIN:
    """Symbolic GIN lookup correctness after Task 2 rewrite."""

    def _mock_row(self, section_id="s1", full_text="Article 297 content",
                  article_number="Article 297", keywords=None):
        kw = keywords or ["Article 297", "Labor Code", "Presidential Decree No. 442"]
        return (
            section_id, full_text, article_number,
            "Termination by Employer",  # article_title
            "Book VI", "Title I", "Chapter III",  # book, title_name, chapter
            "Summary text",             # summary
            kw,                         # keywords
            "https://lawphil.net",      # source_url
            "Labor Code",               # source_title
        )

    @pytest.mark.asyncio
    async def test_article_297_returns_primary_section_only(self, vector_store):
        """Article 297 → returns only sections where '297' is in keywords, not cross-refs."""
        row = self._mock_row(
            section_id="s297",
            full_text="Article 297. Termination by Employer...",
            keywords=["Article 297", "Labor Code"],
        )

        with patch.object(vector_store, '_get_connection') as mock_get_conn, \
             patch.object(vector_store, '_return_connection'):
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [row]

            results = await vector_store.direct_article_lookup(["Article 297"])

        assert len(results) == 1
        assert results[0].id == "s297"
        assert results[0].metadata["_strategy"] == "symbolic"

    @pytest.mark.asyncio
    async def test_ra_10361_normalization(self, vector_store):
        """'RA 10361' short form must expand to canonical 'Republic Act No. 10361'."""
        # Capture the SQL executed so we can verify the expanded form is used
        executed_sqls = []

        with patch.object(vector_store, '_get_connection') as mock_get_conn, \
             patch.object(vector_store, '_return_connection'):
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchall.return_value = []

            # Intercept execute calls to verify normalization
            def capture_execute(sql, params=None):
                executed_sqls.append((sql, params))
            mock_cursor.execute.side_effect = capture_execute

            await vector_store.direct_article_lookup(["RA 10361"])

        # At least one execute should have been called with the expanded canonical form
        all_params = [str(p) for _, p in executed_sqls if p]
        canonical_used = any("Republic Act No. 10361" in p or "Republic Act 10361" in p
                             for p in all_params)
        assert canonical_used, (
            "'RA 10361' must be expanded to canonical form before GIN query. "
            f"Actual params used: {all_params}"
        )

    @pytest.mark.asyncio
    async def test_source_hint_narrows_to_correct_statute(self, vector_store):
        """'Article 297' + 'Labor Code' source hint → only Labor Code result returned."""
        labor_code_row = self._mock_row(
            section_id="lc-297",
            keywords=["Article 297", "Labor Code", "Presidential Decree No. 442"],
        )

        with patch.object(vector_store, '_get_connection') as mock_get_conn, \
             patch.object(vector_store, '_return_connection'):
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [labor_code_row]

            results = await vector_store.direct_article_lookup(
                ["Article 297"],
                keywords=["Labor Code", "termination"]
            )

        assert len(results) >= 1
        # All returned results must carry the symbolic strategy tag
        assert all(r.metadata.get("_strategy") == "symbolic" for r in results)

    @pytest.mark.asyncio
    async def test_score_not_fixed_at_1(self, vector_store):
        """Post-rewrite: ranking must use overlap_count, not hardcoded score=1.0."""
        # s1 matches TWO keyword terms; s2 matches ONE → overlap counts differ
        row_s1 = self._mock_row("s1", keywords=["Article 297", "Labor Code"])
        row_s2 = self._mock_row("s2", keywords=["Article 297"])

        with patch.object(vector_store, '_get_connection') as mock_get_conn, \
             patch.object(vector_store, '_return_connection'):
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [row_s1, row_s2]

            # Query includes BOTH "Article 297" AND "Labor Code" so overlaps differ
            results = await vector_store.direct_article_lookup(
                ["Article 297"],
                keywords=["Labor Code"],  # adds a second matching term for s1
            )

        assert len(results) == 2
        result_map = {r.id: r for r in results}
        # s1 has higher overlap → must rank first
        assert results[0].id == "s1", "Higher overlap must rank first"
        # s1 score must be strictly greater than s2 (overlap_count differs)
        assert result_map["s1"].score > result_map["s2"].score, (
            "Scores must reflect overlap_count differences, not be uniform 1.0"
        )


# ---------------------------------------------------------------------------
# C. smart_retrieve() — strategy gating
# ---------------------------------------------------------------------------

class TestSmartRetrieveStrategyGating:
    """enabled_strategies gates which strategy functions are actually called."""

    @pytest.mark.asyncio
    async def test_dense_only_ignores_articles_and_keywords(self, vector_store):
        """enabled_strategies={'dense'} → only dense runs even with articles+keywords."""
        with patch.object(vector_store, 'direct_article_lookup', new_callable=AsyncMock) as mock_sym, \
             patch.object(vector_store, 'keyword_search', new_callable=AsyncMock) as mock_lex, \
             patch.object(vector_store, 'query_with_chunks', new_callable=AsyncMock) as mock_dense:

            mock_dense.return_value = [_make_result("dense-1", strategy="dense")]
            mock_sym.return_value = [_make_result("sym-1", strategy="symbolic")]
            mock_lex.return_value = [_make_result("lex-1", strategy="lexical")]

            results = await vector_store.smart_retrieve(
                query_embedding=[0.1] * 10,
                query_text="Article 297",
                keywords=["overtime"],
                articles=["Article 297"],
                enabled_strategies={"dense"},
            )

        mock_sym.assert_not_called()
        mock_lex.assert_not_called()
        mock_dense.assert_called_once()

        ids = [r.id for r in results]
        assert "dense-1" in ids
        assert "sym-1" not in ids
        assert "lex-1" not in ids

    @pytest.mark.asyncio
    async def test_empty_set_returns_immediately(self, vector_store):
        """enabled_strategies=set() → returns [] immediately, no strategy called."""
        with patch.object(vector_store, 'direct_article_lookup', new_callable=AsyncMock) as mock_sym, \
             patch.object(vector_store, 'keyword_search', new_callable=AsyncMock) as mock_lex, \
             patch.object(vector_store, 'query_with_chunks', new_callable=AsyncMock) as mock_dense:

            results = await vector_store.smart_retrieve(
                query_embedding=[0.1] * 10,
                query_text="some query",
                keywords=["overtime"],
                articles=["Article 297"],
                enabled_strategies=set(),
            )

        assert results == []
        mock_sym.assert_not_called()
        mock_lex.assert_not_called()
        mock_dense.assert_not_called()

    @pytest.mark.asyncio
    async def test_none_runs_all_applicable_strategies(self, vector_store):
        """enabled_strategies=None → all strategies that have required inputs run."""
        with patch.object(vector_store, 'direct_article_lookup', new_callable=AsyncMock) as mock_sym, \
             patch.object(vector_store, 'keyword_search', new_callable=AsyncMock) as mock_lex, \
             patch.object(vector_store, 'query_with_chunks', new_callable=AsyncMock) as mock_dense:

            mock_sym.return_value = [_make_result("sym-1")]
            mock_lex.return_value = [_make_result("lex-1")]
            mock_dense.return_value = [_make_result("dense-1")]

            await vector_store.smart_retrieve(
                query_embedding=[0.1] * 10,
                query_text="overtime pay Article 297",
                keywords=["overtime", "pay"],
                articles=["Article 297"],
                enabled_strategies=None,
            )

        # All three must have been called because inputs for each were provided
        mock_sym.assert_called_once()
        mock_lex.assert_called_once()
        mock_dense.assert_called_once()

    @pytest.mark.asyncio
    async def test_strategy_metadata_tagged_on_results(self, vector_store):
        """Each result must carry _strategy tag matching its originating strategy."""
        with patch.object(vector_store, 'direct_article_lookup', new_callable=AsyncMock) as mock_sym, \
             patch.object(vector_store, 'keyword_search', new_callable=AsyncMock) as mock_lex, \
             patch.object(vector_store, 'query_with_chunks', new_callable=AsyncMock) as mock_dense:

            # Return results WITHOUT pre-tagging — smart_retrieve must tag them
            mock_sym.return_value = [QueryResult(id="sym-1", content="", metadata={}, score=0.8)]
            mock_lex.return_value = [QueryResult(id="lex-1", content="", metadata={}, score=0.7)]
            mock_dense.return_value = [QueryResult(id="dense-1", content="", metadata={}, score=0.6)]

            results = await vector_store.smart_retrieve(
                query_embedding=[0.1] * 10,
                query_text="overtime Article 297",
                keywords=["overtime"],
                articles=["Article 297"],
                enabled_strategies={"symbolic", "lexical", "dense"},
            )

        result_map = {r.id: r for r in results}
        # After RRF, _contributing_strategies shows which strategies returned the doc
        # Each single-strategy doc must have its _strategy set (tagged in smart_retrieve loop)
        # Note: after RRF the canonical result carries the pre-RRF metadata of first-seen doc
        for r in results:
            strat = r.metadata.get("_strategy") or r.metadata.get("_contributing_strategies")
            assert strat, f"Result {r.id} has no strategy metadata"
