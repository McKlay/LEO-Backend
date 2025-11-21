"""
Manual test script for dual-table retrieval.

Tests the enhanced retrieval with real database queries.
Run this after the backend is started to verify dual-table retrieval works.
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.containers import Container
from core.config import settings


async def test_dual_table_retrieval():
    """Test dual-table retrieval with sample queries."""
    
    # Initialize container
    container = Container()
    
    # Get services
    embeddings = container.embeddings()
    vectorstore = container.vectorstore()
    
    print("=" * 80)
    print("DUAL-TABLE RETRIEVAL TEST")
    print("=" * 80)
    
    # Test queries
    test_queries = [
        "How to calculate overtime pay?",
        "What is 13th month pay?",
        "Article 82 coverage",
        "Night shift differential computation",
        "Employee benefits"
    ]
    
    for query in test_queries:
        print(f"\n{'='*80}")
        print(f"QUERY: {query}")
        print(f"{'='*80}")
        
        # Generate embedding
        embedding_response = await embeddings.embed_text(query)
        query_embedding = embedding_response.embedding
        
        # Test dual-table query
        print("\n1. DUAL-TABLE RETRIEVAL (query_with_chunks)")
        print("-" * 80)
        try:
            dual_results = await vectorstore.query_with_chunks(
                query_embedding=query_embedding,
                limit=5,
                similarity_threshold=0.3
            )
            
            print(f"Found {len(dual_results)} results:")
            for idx, result in enumerate(dual_results, 1):
                source_table = result.metadata.get('_source_table', 'unknown')
                parent_article = result.metadata.get('_parent_article', 'N/A')
                article_number = result.metadata.get('article_number', 'N/A')
                
                print(f"\n  {idx}. [{source_table.upper()}] Score: {result.score:.3f}")
                if source_table == 'chunks':
                    print(f"     Parent: {parent_article}")
                else:
                    print(f"     Article: {article_number}")
                print(f"     Content: {result.content[:150]}...")
                
        except Exception as e:
            print(f"ERROR: {str(e)}")
        
        # Test smart retrieve (uses dual-table for semantic)
        print("\n2. SMART RETRIEVAL (multi-strategy with dual-table)")
        print("-" * 80)
        try:
            smart_results = await vectorstore.smart_retrieve(
                query_embedding=query_embedding,
                query_text=query,
                limit=5,
                threshold=0.3
            )
            
            print(f"Found {len(smart_results)} results:")
            for idx, result in enumerate(smart_results, 1):
                source_table = result.metadata.get('_source_table', 'unknown')
                print(f"\n  {idx}. [{source_table.upper()}] Score: {result.score:.3f}")
                print(f"     Content: {result.content[:150]}...")
                
        except Exception as e:
            print(f"ERROR: {str(e)}")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


async def test_deduplication():
    """Test that parent sections are excluded when chunks are present."""
    
    container = Container()
    embeddings = container.embeddings()
    vectorstore = container.vectorstore()
    
    print("\n" + "=" * 80)
    print("DEDUPLICATION TEST")
    print("=" * 80)
    
    query = "overtime pay calculation formula"
    
    # Generate embedding
    embedding_response = await embeddings.embed_text(query)
    query_embedding = embedding_response.embedding
    
    # Get results
    results = await vectorstore.query_with_chunks(
        query_embedding=query_embedding,
        limit=10,
        similarity_threshold=0.3
    )
    
    # Check for parent-child duplicates
    section_ids = []
    chunk_section_ids = []
    
    for result in results:
        source_table = result.metadata.get('_source_table')
        if source_table == 'sections':
            section_ids.append(result.id)
        elif source_table == 'chunks':
            parent_id = result.metadata.get('section_id')
            if parent_id:
                chunk_section_ids.append(parent_id)
    
    # Find duplicates (sections that also have chunks)
    duplicates = set(section_ids).intersection(set(chunk_section_ids))
    
    print(f"\nTotal results: {len(results)}")
    print(f"Sections: {len(section_ids)}")
    print(f"Chunks: {len(chunk_section_ids)}")
    print(f"Duplicate parent-child pairs: {len(duplicates)}")
    
    if duplicates:
        print("\n⚠️  WARNING: Found duplicate parent-child pairs!")
        for dup_id in duplicates:
            print(f"   - {dup_id}")
    else:
        print("\n✅ PASSED: No duplicate parent-child pairs found")
    
    print("=" * 80)


async def test_ranking_priority():
    """Test that ranking prioritizes chunks over sections correctly."""
    
    container = Container()
    embeddings = container.embeddings()
    vectorstore = container.vectorstore()
    
    print("\n" + "=" * 80)
    print("RANKING PRIORITY TEST")
    print("=" * 80)
    
    query = "how to compute overtime"
    
    # Generate embedding
    embedding_response = await embeddings.embed_text(query)
    query_embedding = embedding_response.embedding
    
    # Get results
    results = await vectorstore.query_with_chunks(
        query_embedding=query_embedding,
        limit=10,
        similarity_threshold=0.3
    )
    
    print(f"\nRanking order ({len(results)} results):")
    for idx, result in enumerate(results, 1):
        source_table = result.metadata.get('_source_table', 'unknown')
        score = result.score
        
        # Determine expected priority
        if source_table == 'chunks':
            if score > 0.85:
                priority = 4
            elif score > 0.75:
                priority = 2
            else:
                priority = 0
        else:  # sections
            if score > 0.80:
                priority = 3
            elif score > 0.70:
                priority = 1
            else:
                priority = 0
        
        print(f"  {idx}. [{source_table.upper():8}] Score: {score:.3f} | Priority: {priority}")
    
    # Verify ranking is correct (higher priority first)
    is_valid = True
    for i in range(len(results) - 1):
        current = results[i]
        next_result = results[i + 1]
        
        # Calculate priorities (same logic as in code)
        current_priority = _calculate_priority(current)
        next_priority = _calculate_priority(next_result)
        
        if current_priority < next_priority:
            print(f"\n⚠️  RANKING ERROR at position {i+1}")
            print(f"   Current: priority={current_priority}, score={current.score}")
            print(f"   Next: priority={next_priority}, score={next_result.score}")
            is_valid = False
    
    if is_valid:
        print("\n✅ PASSED: Ranking is correct")
    else:
        print("\n❌ FAILED: Ranking has errors")
    
    print("=" * 80)


def _calculate_priority(result) -> int:
    """Calculate ranking priority for a result."""
    source_table = result.metadata.get('_source_table', 'unknown')
    score = result.score
    
    if source_table == 'chunks':
        if score > 0.85:
            return 4
        elif score > 0.75:
            return 2
        else:
            return 0
    else:  # sections
        if score > 0.80:
            return 3
        elif score > 0.70:
            return 1
        else:
            return 0


if __name__ == "__main__":
    print("Starting dual-table retrieval tests...")
    print("Make sure the backend is running and database is populated.\n")
    
    asyncio.run(test_dual_table_retrieval())
    asyncio.run(test_deduplication())
    asyncio.run(test_ranking_priority())
    
    print("\n✅ All tests completed!")
