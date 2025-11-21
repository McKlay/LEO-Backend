"""
Unit tests for dual-table retrieval (sections + chunks).

Tests the new query_with_chunks() method in SupabaseVectorStore.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
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
    settings.enable_connection_pooling = False  # Disable for unit tests
    return settings


@pytest.fixture
def vectorstore(mock_supabase_client, mock_settings):
    """Create SupabaseVectorStore instance."""
    return SupabaseVectorStore(mock_supabase_client, mock_settings)


@pytest.mark.asyncio
async def test_query_sections_table(vectorstore):
    """Test querying labor_law_sections table."""
    query_embedding = [0.1] * 1536
    
    # Mock database connection and cursor
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_cursor.fetchall.return_value = [
        (
            "section-123",
            "Article 82. Coverage. This title shall apply to employees...",
            {"article_number": "Article 82", "title": "Coverage"},
            0.85
        )
    ]
    
    with patch.object(vectorstore, '_get_connection', return_value=mock_conn):
        with patch.object(vectorstore, '_return_connection'):
            mock_conn.cursor.return_value = mock_cursor
            
            results = await vectorstore._query_sections_table(
                query_embedding, limit=10, threshold=0.7
            )
    
    assert len(results) == 1
    assert results[0].id == "section-123"
    assert results[0].score == 0.85
    assert results[0].metadata['_source_table'] == 'sections'
    assert "Article 82" in results[0].content


@pytest.mark.asyncio
async def test_query_chunks_table(vectorstore):
    """Test querying labor_law_chunks table."""
    query_embedding = [0.1] * 1536
    
    # Mock database connection and cursor
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_cursor.fetchall.return_value = [
        (
            "chunk-456",
            "Overtime pay shall be computed as follows: (a) Regular workday...",
            {"chunk_index": 0, "section_id": "section-123"},
            0.92,
            "Article 87",
            "Overtime Work"
        )
    ]
    
    with patch.object(vectorstore, '_get_connection', return_value=mock_conn):
        with patch.object(vectorstore, '_return_connection'):
            mock_conn.cursor.return_value = mock_cursor
            
            results = await vectorstore._query_chunks_table(
                query_embedding, limit=10, threshold=0.7
            )
    
    assert len(results) == 1
    assert results[0].id == "chunk-456"
    assert results[0].score == 0.92
    assert results[0].metadata['_source_table'] == 'chunks'
    assert results[0].metadata['_parent_article'] == "Article 87"
    assert "Overtime pay" in results[0].content


@pytest.mark.asyncio
async def test_merge_and_rank_dual_table(vectorstore):
    """Test merging and ranking results from both tables."""
    # Create mock sections
    sections = [
        QueryResult(
            id="section-1",
            content="Full article content",
            metadata={"_source_table": "sections"},
            score=0.82
        ),
        QueryResult(
            id="section-2",
            content="Another article",
            metadata={"_source_table": "sections"},
            score=0.75
        )
    ]
    
    # Create mock chunks (one is child of section-1)
    chunks = [
        QueryResult(
            id="chunk-1",
            content="Specific formula for overtime",
            metadata={"_source_table": "chunks", "section_id": "section-1"},
            score=0.88
        ),
        QueryResult(
            id="chunk-2",
            content="Holiday pay computation",
            metadata={"_source_table": "chunks", "section_id": "section-3"},
            score=0.79
        )
    ]
    
    # Merge and rank
    results = vectorstore._merge_and_rank_dual_table(sections, chunks, limit=10)
    
    # Assertions
    assert len(results) == 3  # 3 results (section-1 excluded due to chunk-1)
    
    # Check priority ranking (based on scoring algorithm):
    # chunk-1 (0.88) should be first (chunks >0.85 = priority 4)
    assert results[0].id == "chunk-1"
    assert results[0].score == 0.88
    
    # section-2 (0.75) has priority 0 (below 0.70 threshold for sections)
    # chunk-2 (0.79) has priority 2 (chunks >0.75)
    # So chunk-2 should be second
    assert results[1].id == "chunk-2"
    
    # section-2 should be third
    assert results[2].id == "section-2"
    
    # section-1 should NOT be in results (has child chunk)
    result_ids = [r.id for r in results]
    assert "section-1" not in result_ids


@pytest.mark.asyncio
async def test_query_with_chunks_integration(vectorstore):
    """Test full dual-table query integration."""
    query_embedding = [0.1] * 1536
    
    # Mock both table queries
    sections = [
        QueryResult(
            id="section-1",
            content="Full article",
            metadata={"_source_table": "sections"},
            score=0.80
        )
    ]
    
    chunks = [
        QueryResult(
            id="chunk-1",
            content="Specific chunk",
            metadata={"_source_table": "chunks", "section_id": "section-2"},
            score=0.90
        )
    ]
    
    with patch.object(vectorstore, '_query_sections_table', return_value=sections):
        with patch.object(vectorstore, '_query_chunks_table', return_value=chunks):
            results = await vectorstore.query_with_chunks(
                query_embedding, limit=10, similarity_threshold=0.7
            )
    
    assert len(results) == 2
    # chunk-1 should be first (higher score)
    assert results[0].id == "chunk-1"
    assert results[0].score == 0.90


@pytest.mark.asyncio
async def test_query_with_chunks_error_handling(vectorstore):
    """Test error handling when one table query fails."""
    query_embedding = [0.1] * 1536
    
    # Mock sections query to succeed
    sections = [
        QueryResult(
            id="section-1",
            content="Full article",
            metadata={"_source_table": "sections"},
            score=0.80
        )
    ]
    
    # Mock chunks query to fail
    with patch.object(vectorstore, '_query_sections_table', return_value=sections):
        with patch.object(
            vectorstore, '_query_chunks_table', 
            side_effect=Exception("Database error")
        ):
            results = await vectorstore.query_with_chunks(
                query_embedding, limit=10, similarity_threshold=0.7
            )
    
    # Should still return sections results
    assert len(results) == 1
    assert results[0].id == "section-1"


@pytest.mark.asyncio
async def test_smart_retrieve_uses_dual_table(vectorstore):
    """Test that smart_retrieve uses query_with_chunks for semantic search."""
    query_embedding = [0.1] * 1536
    query_text = "What is overtime pay?"
    
    # Mock query_with_chunks to verify it's called
    dual_results = [
        QueryResult(
            id="chunk-1",
            content="Overtime formula",
            metadata={"_source_table": "chunks"},
            score=0.90
        )
    ]
    
    with patch.object(vectorstore, 'query_with_chunks', return_value=dual_results) as mock_dual:
        results = await vectorstore.smart_retrieve(
            query_embedding=query_embedding,
            query_text=query_text,
            limit=10,
            threshold=0.3
        )
    
    # Verify query_with_chunks was called
    mock_dual.assert_called_once()
    assert len(results) == 1
    assert results[0].id == "chunk-1"


@pytest.mark.asyncio
async def test_deduplication_prevents_parent_and_child(vectorstore):
    """Test that parent section is excluded when its chunk is included."""
    # Parent section
    sections = [
        QueryResult(
            id="parent-section",
            content="Full article with subsections",
            metadata={"_source_table": "sections"},
            score=0.75
        )
    ]
    
    # Child chunk with section_id pointing to parent
    chunks = [
        QueryResult(
            id="child-chunk",
            content="Specific subsection content",
            metadata={"_source_table": "chunks", "section_id": "parent-section"},
            score=0.85
        )
    ]
    
    results = vectorstore._merge_and_rank_dual_table(sections, chunks, limit=10)
    
    # Should only have chunk, not parent section
    assert len(results) == 1
    assert results[0].id == "child-chunk"
    
    result_ids = [r.id for r in results]
    assert "parent-section" not in result_ids
