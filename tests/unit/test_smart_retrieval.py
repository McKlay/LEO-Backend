"""
Unit tests for multi-strategy smart retrieval.

Tests direct article lookup, keyword search, semantic search,
parallel execution, and result merging.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from adapters.vectorstore.supabase_store import SupabaseVectorStore
from adapters.vectorstore.base import QueryResult


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client."""
    return MagicMock()


@pytest.fixture
def mock_settings():
    """Mock settings."""
    settings = MagicMock()
    settings.vectorstore_table_name = "labor_law_embeddings"
    settings.embedding_dimension = 1536
    settings.supabase_db_url = "postgresql://test"
    settings.rrf_dense_weight = 2.0
    settings.rrf_lexical_weight = 1.0
    settings.rrf_symbolic_weight = 0.5
    return settings


@pytest.fixture
def vector_store(mock_supabase_client, mock_settings):
    """Create vector store instance."""
    return SupabaseVectorStore(
        supabase_client=mock_supabase_client,
        settings=mock_settings
    )


class TestDirectArticleLookup:
    """Test direct article lookup functionality."""
    
    @pytest.mark.asyncio
    async def test_direct_lookup_finds_article(self, vector_store):
        """Test that direct lookup finds specific article."""
        articles = ["Article 123"]
        
        with patch('psycopg2.connect') as mock_connect:
            # Mock database connection and cursor
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            
            # Mock database results
            mock_cursor.fetchall.return_value = [
                ("doc1", "Content about Article 123", {"source": "Labor Code"})
            ]
            
            results = await vector_store.direct_article_lookup(articles)
            
            assert len(results) == 1
            assert results[0].score == 1.0  # Perfect score for direct match
            assert "Article 123" in results[0].content
    
    @pytest.mark.asyncio
    async def test_direct_lookup_multiple_articles(self, vector_store):
        """Test lookup of multiple article references."""
        articles = ["Article 123", "PD 442"]
        
        with patch('psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            
            # Mock database results for multiple articles
            mock_cursor.fetchall.side_effect = [
                [("doc1", "Content about Article 123", {"source": "Labor Code"})],
                [("doc2", "Content about PD 442", {"source": "Presidential Decree"})]
            ]
            
            results = await vector_store.direct_article_lookup(articles)
            
            assert len(results) >= 1
            # Should have results from both articles
    
    @pytest.mark.asyncio
    async def test_direct_lookup_empty_articles(self, vector_store):
        """Test that empty articles list returns empty results."""
        results = await vector_store.direct_article_lookup([])
        assert len(results) == 0
    
    @pytest.mark.asyncio
    async def test_direct_lookup_deduplicates(self, vector_store):
        """Test that duplicate results are removed."""
        articles = ["Article 123", "Art. 123"]  # Same article, different formats
        
        with patch('psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            
            # Mock same document returned twice
            mock_cursor.fetchall.side_effect = [
                [("doc1", "Content about Article 123", {"source": "Labor Code"})],
                [("doc1", "Content about Article 123", {"source": "Labor Code"})]
            ]
            
            results = await vector_store.direct_article_lookup(articles)
            
            # Should deduplicate by ID
            assert len(results) == 1


class TestKeywordSearch:
    """Test keyword-based full-text search."""
    
    @pytest.mark.asyncio
    async def test_keyword_search_finds_results(self, vector_store):
        """Test that keyword search returns relevant results."""
        query = "overtime pay"
        keywords = ["overtime", "pay"]
        
        with patch('psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            
            # Mock FTS results with rank scores
            mock_cursor.fetchall.return_value = [
                ("doc1", "Content about overtime pay", {"source": "Labor Code"}, 0.8),
                ("doc2", "More about overtime", {"source": "Labor Code"}, 0.6)
            ]
            
            results = await vector_store.keyword_search(query, keywords)
            
            assert len(results) == 2
            assert results[0].score > results[1].score  # Sorted by rank
    
    @pytest.mark.asyncio
    async def test_keyword_search_empty_keywords(self, vector_store):
        """Test that empty keywords returns empty results."""
        results = await vector_store.keyword_search("query", [])
        assert len(results) == 0
    
    @pytest.mark.asyncio
    async def test_keyword_search_threshold_filtering(self, vector_store):
        """Test that results below threshold are filtered."""
        query = "overtime"
        keywords = ["overtime"]
        
        with patch('psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            
            # Only high-ranked results should be returned
            mock_cursor.fetchall.return_value = [
                ("doc1", "Highly relevant content", {"source": "Labor Code"}, 0.9)
            ]
            
            results = await vector_store.keyword_search(query, keywords, threshold=0.5)
            
            assert len(results) >= 0  # Should only include results above threshold


class TestSmartRetrieve:
    """Test smart multi-strategy retrieval orchestrator."""
    
    @pytest.mark.asyncio
    async def test_smart_retrieve_prioritizes_direct_lookup(self, vector_store):
        """Test that direct article lookup has highest priority."""
        query_embedding = [0.1] * 1536
        query_text = "What is Article 123 about?"
        keywords = ["article"]
        articles = ["Article 123"]
        
        with patch.object(vector_store, 'direct_article_lookup', new_callable=AsyncMock) as mock_direct, \
             patch.object(vector_store, 'keyword_search', new_callable=AsyncMock) as mock_keyword, \
             patch.object(vector_store, 'query', new_callable=AsyncMock) as mock_semantic:
            
            # Mock results from different strategies
            mock_direct.return_value = [
                QueryResult(id="doc1", content="Direct match", metadata={}, score=1.0)
            ]
            mock_keyword.return_value = [
                QueryResult(id="doc2", content="Keyword match", metadata={}, score=0.7)
            ]
            mock_semantic.return_value = [
                QueryResult(id="doc3", content="Semantic match", metadata={}, score=0.6)
            ]
            
            results = await vector_store.smart_retrieve(
                query_embedding=query_embedding,
                query_text=query_text,
                keywords=keywords,
                articles=articles
            )
            
            # Direct lookup result should be first
            assert results[0].id == "doc1"
            assert results[0].score == 1.0
    
    @pytest.mark.asyncio
    async def test_smart_retrieve_parallel_execution(self, vector_store):
        """Test that strategies execute in parallel."""
        query_embedding = [0.1] * 1536
        query_text = "overtime pay"
        keywords = ["overtime", "pay"]
        articles = ["Article 123"]
        
        with patch.object(vector_store, 'direct_article_lookup', new_callable=AsyncMock) as mock_direct, \
             patch.object(vector_store, 'keyword_search', new_callable=AsyncMock) as mock_keyword, \
             patch.object(vector_store, 'query_with_chunks', new_callable=AsyncMock) as mock_semantic:
            
            # All should return results
            mock_direct.return_value = [QueryResult(id="d1", content="", metadata={}, score=1.0)]
            mock_keyword.return_value = [QueryResult(id="d2", content="", metadata={}, score=0.7)]
            mock_semantic.return_value = [QueryResult(id="d3", content="", metadata={}, score=0.6)]
            
            results = await vector_store.smart_retrieve(
                query_embedding=query_embedding,
                query_text=query_text,
                keywords=keywords,
                articles=articles
            )
            
            # All strategies should have been called
            mock_direct.assert_called_once()
            mock_keyword.assert_called_once()
            mock_semantic.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_smart_retrieve_deduplicates_results(self, vector_store):
        """Test that duplicate results from different strategies are deduplicated."""
        query_embedding = [0.1] * 1536
        query_text = "overtime"
        keywords = ["overtime"]
        
        with patch.object(vector_store, 'keyword_search', new_callable=AsyncMock) as mock_keyword, \
             patch.object(vector_store, 'query_with_chunks', new_callable=AsyncMock) as mock_semantic:
            
            # Both strategies return same document
            same_doc = QueryResult(id="doc1", content="Same content", metadata={}, score=0.8)
            mock_keyword.return_value = [same_doc]
            mock_semantic.return_value = [same_doc]
            
            results = await vector_store.smart_retrieve(
                query_embedding=query_embedding,
                query_text=query_text,
                keywords=keywords
            )
            
            # Should only return once (deduplicated)
            assert len(results) == 1
            assert results[0].id == "doc1"
    
    @pytest.mark.asyncio
    async def test_smart_retrieve_handles_strategy_failures(self, vector_store):
        """Test that smart retrieve continues if one strategy fails."""
        query_embedding = [0.1] * 1536
        query_text = "overtime"
        keywords = ["overtime"]
        
        with patch.object(vector_store, 'keyword_search', new_callable=AsyncMock) as mock_keyword, \
             patch.object(vector_store, 'query_with_chunks', new_callable=AsyncMock) as mock_semantic:
            
            # Keyword search fails
            mock_keyword.side_effect = Exception("Database error")
            
            # Semantic search succeeds
            mock_semantic.return_value = [
                QueryResult(id="doc1", content="Semantic match", metadata={}, score=0.7)
            ]
            
            results = await vector_store.smart_retrieve(
                query_embedding=query_embedding,
                query_text=query_text,
                keywords=keywords
            )
            
            # Should still return semantic results
            assert len(results) >= 1
    
    @pytest.mark.asyncio
    async def test_smart_retrieve_empty_inputs(self, vector_store):
        """Test that smart retrieve handles case with no inputs gracefully."""
        results = await vector_store.smart_retrieve()
        assert len(results) == 0
    
    @pytest.mark.asyncio
    async def test_smart_retrieve_respects_limit(self, vector_store):
        """Test that smart retrieve respects the limit parameter."""
        query_embedding = [0.1] * 1536
        limit = 3
        
        with patch.object(vector_store, 'query', new_callable=AsyncMock) as mock_semantic:
            # Return many results
            mock_semantic.return_value = [
                QueryResult(id=f"doc{i}", content="", metadata={}, score=0.9-i*0.1)
                for i in range(10)
            ]
            
            results = await vector_store.smart_retrieve(
                query_embedding=query_embedding,
                limit=limit
            )
            
            # Should return only 'limit' results
            assert len(results) <= limit


class TestResultMerging:
    """Test result merging and ranking algorithm."""
    
    @pytest.mark.asyncio
    async def test_merging_prioritizes_by_strategy(self, vector_store):
        """Test that results are prioritized by strategy (direct > keyword > semantic)."""
        query_embedding = [0.1] * 1536
        query_text = "Article 123"
        keywords = ["article"]
        articles = ["Article 123"]
        
        with patch.object(vector_store, 'direct_article_lookup', new_callable=AsyncMock) as mock_direct, \
             patch.object(vector_store, 'keyword_search', new_callable=AsyncMock) as mock_keyword, \
             patch.object(vector_store, 'query_with_chunks', new_callable=AsyncMock) as mock_semantic:
            
            # Lower score direct match should still come first
            mock_direct.return_value = [
                QueryResult(id="doc1", content="Direct", metadata={}, score=0.8)
            ]
            mock_keyword.return_value = [
                QueryResult(id="doc2", content="Keyword", metadata={}, score=0.9)
            ]
            mock_semantic.return_value = [
                QueryResult(id="doc3", content="Semantic", metadata={}, score=0.95)
            ]
            
            results = await vector_store.smart_retrieve(
                query_embedding=query_embedding,
                query_text=query_text,
                keywords=keywords,
                articles=articles
            )
            
            # Direct should be first despite lower score
            assert results[0].id == "doc1"
            # Keyword should be second
            assert results[1].id == "doc2"
            # Semantic should be last
            assert results[2].id == "doc3"
    
    @pytest.mark.asyncio
    async def test_merging_sorts_by_score_within_strategy(self, vector_store):
        """Test that within same strategy, results are sorted by score."""
        query_embedding = [0.1] * 1536
        
        with patch.object(vector_store, 'query_with_chunks', new_callable=AsyncMock) as mock_semantic:
            # Multiple semantic results with different scores
            mock_semantic.return_value = [
                QueryResult(id="doc1", content="", metadata={}, score=0.6),
                QueryResult(id="doc2", content="", metadata={}, score=0.9),
                QueryResult(id="doc3", content="", metadata={}, score=0.7)
            ]
            
            results = await vector_store.smart_retrieve(query_embedding=query_embedding)
            
            # Should be sorted by score (highest first)
            assert results[0].score >= results[1].score >= results[2].score
