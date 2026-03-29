"""
Unit tests for retrieval ranking algorithm.

Tests the priority-based ranking system for sections vs chunks.
"""
import pytest
from unittest.mock import Mock
from adapters.vectorstore.supabase_store import SupabaseVectorStore
from adapters.vectorstore.base import QueryResult


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client."""
    return Mock()


@pytest.fixture
def mock_settings():
    """Mock settings."""
    settings = Mock()
    settings.vectorstore_table_name = "labor_law_sections"
    settings.embedding_dimension = 1536
    settings.supabase_db_url = "postgresql://test:test@localhost/test"
    settings.enable_connection_pooling = False
    return settings


@pytest.fixture
def vectorstore(mock_supabase_client, mock_settings):
    """Create SupabaseVectorStore instance."""
    return SupabaseVectorStore(mock_supabase_client, mock_settings)


class TestRankingPriority:
    """Test priority-based ranking algorithm."""
    
    def test_chunks_above_085_highest_priority(self, vectorstore):
        """Test that chunks with >0.85 similarity get highest priority."""
        sections = [
            QueryResult(
                id="section-1",
                content="Full article",
                metadata={"_source_table": "sections"},
                score=0.90  # High score but sections priority lower
            )
        ]
        
        chunks = [
            QueryResult(
                id="chunk-1",
                content="Specific detail",
                metadata={"_source_table": "chunks", "section_id": "other"},
                score=0.87  # >0.85, should be first
            )
        ]
        
        results = vectorstore._merge_and_rank_dual_table(sections, chunks, limit=10)
        
        # Chunk should be first despite section having higher raw score
        assert results[0].id == "chunk-1"
        assert results[1].id == "section-1"
    
    def test_sections_above_080_second_priority(self, vectorstore):
        """Test sections >0.80 have second priority."""
        sections = [
            QueryResult(
                id="section-1",
                content="Full article",
                metadata={"_source_table": "sections"},
                score=0.82
            )
        ]
        
        chunks = [
            QueryResult(
                id="chunk-1",
                content="Detail",
                metadata={"_source_table": "chunks", "section_id": "other"},
                score=0.78  # <0.85, lower priority
            )
        ]
        
        results = vectorstore._merge_and_rank_dual_table(sections, chunks, limit=10)
        
        # Section should be first (priority 1 vs priority 2)
        assert results[0].id == "section-1"
        assert results[1].id == "chunk-1"
    
    def test_chunks_above_075_third_priority(self, vectorstore):
        """Test chunks >0.75 have third priority."""
        sections = [
            QueryResult(
                id="section-1",
                content="Full article",
                metadata={"_source_table": "sections"},
                score=0.72  # <0.80, lower priority
            )
        ]
        
        chunks = [
            QueryResult(
                id="chunk-1",
                content="Detail",
                metadata={"_source_table": "chunks", "section_id": "other"},
                score=0.77  # >0.75, higher priority
            )
        ]
        
        results = vectorstore._merge_and_rank_dual_table(sections, chunks, limit=10)
        
        # Chunk should be first
        assert results[0].id == "chunk-1"
        assert results[1].id == "section-1"
    
    def test_sections_above_070_fourth_priority(self, vectorstore):
        """Test sections >0.70 have fourth priority."""
        sections = [
            QueryResult(
                id="section-1",
                content="Full article",
                metadata={"_source_table": "sections"},
                score=0.71
            )
        ]
        
        chunks = [
            QueryResult(
                id="chunk-1",
                content="Detail",
                metadata={"_source_table": "chunks", "section_id": "other"},
                score=0.68  # Below all thresholds
            )
        ]
        
        results = vectorstore._merge_and_rank_dual_table(sections, chunks, limit=10)
        
        # Section should be first
        assert results[0].id == "section-1"
        assert results[1].id == "chunk-1"
    
    def test_same_priority_sorts_by_score(self, vectorstore):
        """Test that within the same priority tier, results are sorted by score descending."""
        chunks = [
            QueryResult(
                id="chunk-1",
                content="Detail 1",
                metadata={"_source_table": "chunks", "section_id": "s1"},
                score=0.87
            ),
            QueryResult(
                id="chunk-2",
                content="Detail 2",
                metadata={"_source_table": "chunks", "section_id": "s2"},
                score=0.92
            ),
            QueryResult(
                id="chunk-3",
                content="Detail 3",
                metadata={"_source_table": "chunks", "section_id": "s3"},
                score=0.89
            )
        ]
        
        results = vectorstore._merge_and_rank_dual_table([], chunks, limit=10)
        
        # All fall in the same priority tier (>0.85 chunks → priority 4).
        # Within a tier, sort must be descending by score.
        assert len(results) == 3
        assert [r.id for r in results] == ["chunk-2", "chunk-3", "chunk-1"]  # 0.92, 0.89, 0.87
    
    def test_complex_mixed_ranking(self, vectorstore):
        """Test complex scenario with multiple priorities."""
        sections = [
            QueryResult(
                id="section-1",
                content="Article A",
                metadata={"_source_table": "sections"},
                score=0.82  # Priority 1
            ),
            QueryResult(
                id="section-2",
                content="Article B",
                metadata={"_source_table": "sections"},
                score=0.71  # Priority 3
            )
        ]
        
        chunks = [
            QueryResult(
                id="chunk-1",
                content="Detail A",
                metadata={"_source_table": "chunks", "section_id": "other"},
                score=0.88  # Priority 4 (highest)
            ),
            QueryResult(
                id="chunk-2",
                content="Detail B",
                metadata={"_source_table": "chunks", "section_id": "other"},
                score=0.76  # Priority 2
            ),
            QueryResult(
                id="chunk-3",
                content="Detail C",
                metadata={"_source_table": "chunks", "section_id": "other"},
                score=0.65  # Priority 0 (lowest)
            )
        ]
        
        results = vectorstore._merge_and_rank_dual_table(sections, chunks, limit=10)
        
        # Expected order: chunk-1 (P4) > section-1 (P3) > chunk-2 (P2) > section-2 (P1) > chunk-3 (P0)
        expected_order = ["chunk-1", "section-1", "chunk-2", "section-2", "chunk-3"]
        actual_order = [r.id for r in results]
        
        assert actual_order == expected_order
    
    def test_tier0_real_kb_scores_sorted_descending(self, vectorstore):
        """
        Regression test: all scores below 0.70 (real KB range) must be sorted
        descending within tier 0. The previous bug (ranking_key returned
        (priority, -score) with reverse=True) caused ascending order here,
        returning the worst matches first.
        """
        sections = [
            QueryResult(id="gold", content="Gold article", metadata={"_source_table": "sections"}, score=0.50),
            QueryResult(id="low-1", content="Irrelevant", metadata={"_source_table": "sections"}, score=0.31),
            QueryResult(id="low-2", content="Irrelevant", metadata={"_source_table": "sections"}, score=0.33),
        ]
        chunks = [
            QueryResult(id="best-chunk", content="Best chunk", metadata={"_source_table": "chunks", "section_id": "other"}, score=0.57),
            QueryResult(id="mid-chunk", content="Mid chunk", metadata={"_source_table": "chunks", "section_id": "other2"}, score=0.45),
        ]
        
        results = vectorstore._merge_and_rank_dual_table(sections, chunks, limit=5)
        
        # Must be descending by score; gold section at 0.50 must appear before low-scoring items
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True), f"Expected descending scores, got {scores}"
        assert results[0].id == "best-chunk"  # 0.57
        assert results[1].id == "gold"        # 0.50


class TestChunkMetadata:
    """Test chunk metadata enrichment."""
    
    def test_chunk_has_parent_article_info(self, vectorstore):
        """Test that chunks include parent article information."""
        chunks = [
            QueryResult(
                id="chunk-1",
                content="Overtime calculation",
                metadata={
                    "_source_table": "chunks",
                    "section_id": "section-123",
                    "_parent_article": "Article 87",
                    "_parent_title": "Overtime Work"
                },
                score=0.90
            )
        ]
        
        results = vectorstore._merge_and_rank_dual_table([], chunks, limit=10)
        
        assert results[0].metadata["_parent_article"] == "Article 87"
        assert results[0].metadata["_parent_title"] == "Overtime Work"
    
    def test_section_has_source_table_marker(self, vectorstore):
        """Test that sections include source table marker."""
        sections = [
            QueryResult(
                id="section-1",
                content="Full article",
                metadata={
                    "_source_table": "sections",
                    "article_number": "Article 82"
                },
                score=0.85
            )
        ]
        
        results = vectorstore._merge_and_rank_dual_table(sections, [], limit=10)
        
        assert results[0].metadata["_source_table"] == "sections"
        assert results[0].metadata["article_number"] == "Article 82"


class TestLimitHandling:
    """Test limit parameter handling."""
    
    def test_respects_limit_parameter(self, vectorstore):
        """Test that limit parameter is respected."""
        sections = [
            QueryResult(
                id=f"section-{i}",
                content=f"Article {i}",
                metadata={"_source_table": "sections"},
                score=0.80 - (i * 0.01)
            )
            for i in range(10)
        ]
        
        results = vectorstore._merge_and_rank_dual_table(sections, [], limit=5)
        
        # Should limit to 5 results
        assert len(results) == 5
        # All results should have same priority (>0.70)
        # Note: algorithm uses priority buckets, not pure score sorting
    
    def test_empty_results_with_limit(self, vectorstore):
        """Test that empty inputs return empty results."""
        results = vectorstore._merge_and_rank_dual_table([], [], limit=10)
        assert len(results) == 0
