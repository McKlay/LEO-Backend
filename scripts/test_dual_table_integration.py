"""
Manual integration test for dual-table retrieval with real ingested data.

Run with backend running: python scripts/test_dual_table_integration.py
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.containers import (
    get_embeddings_adapter,
    get_vectorstore_adapter
)


async def test_ingested_documents():
    """Test retrieval with actual ingested documents."""
    
    embeddings = get_embeddings_adapter()
    vectorstore = get_vectorstore_adapter()
    
    print("\n" + "="*80)
    print("DUAL-TABLE RETRIEVAL TEST - INGESTED DOCUMENTS")
    print("="*80)
    
    # Test queries based on ingested documents
    test_cases = [
        {
            "query": "What is 13th month pay?",
            "expected_source": "PD-851",
            "expect_chunks": True,
            "description": "Should retrieve PD-851 sections/chunks about 13th month pay"
        },
        {
            "query": "How to compute 13th month pay?",
            "expected_source": "PD-851",
            "expect_chunks": True,
            "description": "Should retrieve PD-851 chunks with computation details"
        },
        {
            "query": "Who is a kasambahay?",
            "expected_source": "RA-10362",
            "expect_chunks": False,
            "description": "Should retrieve RA-10362 definition section"
        },
        {
            "query": "What is overtime pay?",
            "expected_source": "PD-442",
            "expect_chunks": True,
            "description": "Should retrieve Labor Code overtime sections/chunks"
        },
        {
            "query": "Night shift differential rate",
            "expected_source": "PD-442",
            "expect_chunks": True,
            "description": "Should retrieve Labor Code night diff chunks"
        }
    ]
    
    for idx, test in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"TEST {idx}: {test['query']}")
        print(f"Expected: {test['description']}")
        print(f"{'='*80}")
        
        try:
            # Generate embedding
            embedding_response = await embeddings.embed_text(test['query'])
            query_embedding = embedding_response.embedding
            
            # Test dual-table retrieval
            results = await vectorstore.query_with_chunks(
                query_embedding=query_embedding,
                limit=5,
                similarity_threshold=0.3
            )
            
            print(f"\n✓ Retrieved {len(results)} results")
            
            if len(results) == 0:
                print("⚠️  WARNING: No results found!")
                continue
            
            # Analyze results
            sections_count = sum(1 for r in results if r.metadata.get('_source_table') == 'sections')
            chunks_count = sum(1 for r in results if r.metadata.get('_source_table') == 'chunks')
            
            print(f"  - Sections: {sections_count}")
            print(f"  - Chunks: {chunks_count}")
            
            # Check sources
            sources = set()
            for result in results:
                source = result.metadata.get('source_reference', 
                         result.metadata.get('_parent_article', 'Unknown'))
                sources.add(source)
            
            print(f"  - Sources found: {', '.join(sources)}")
            
            # Display top result
            top_result = results[0]
            source_table = top_result.metadata.get('_source_table', 'unknown')
            print(f"\n  Top Result ({source_table.upper()}):")
            print(f"    Score: {top_result.score:.3f}")
            print(f"    Content: {top_result.content[:200]}...")
            
            # Verify expectations
            if test['expect_chunks']:
                if chunks_count > 0:
                    print(f"  ✓ PASS: Chunks retrieved as expected")
                else:
                    print(f"  ⚠️  WARNING: Expected chunks but none found")
            
        except Exception as e:
            print(f"  ❌ ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*80}")
    print("TESTS COMPLETE")
    print(f"{'='*80}\n")


async def test_deduplication():
    """Test deduplication with real data."""
    
    embeddings = get_embeddings_adapter()
    vectorstore = get_vectorstore_adapter()
    
    print("\n" + "="*80)
    print("DEDUPLICATION TEST - REAL DATA")
    print("="*80)
    
    query = "overtime pay computation"
    
    embedding_response = await embeddings.embed_text(query)
    query_embedding = embedding_response.embedding
    
    results = await vectorstore.query_with_chunks(
        query_embedding=query_embedding,
        limit=10,
        similarity_threshold=0.3
    )
    
    print(f"\n✓ Retrieved {len(results)} results for: '{query}'")
    
    # Check for parent-child duplicates
    section_ids = set()
    chunk_parent_ids = set()
    
    for result in results:
        source_table = result.metadata.get('_source_table')
        if source_table == 'sections':
            section_ids.add(result.id)
        elif source_table == 'chunks':
            parent_id = result.metadata.get('section_id')
            if parent_id:
                chunk_parent_ids.add(parent_id)
    
    duplicates = section_ids.intersection(chunk_parent_ids)
    
    print(f"\nDeduplication Analysis:")
    print(f"  - Total sections: {len(section_ids)}")
    print(f"  - Total chunks: {len(chunk_parent_ids)}")
    print(f"  - Duplicate parent-child pairs: {len(duplicates)}")
    
    if duplicates:
        print(f"\n  ⚠️  WARNING: Found {len(duplicates)} duplicate parent-child pairs")
    else:
        print(f"\n  ✓ PASS: No duplicate parent-child pairs found")
    
    print("="*80 + "\n")


async def test_ranking():
    """Test ranking with real data."""
    
    embeddings = get_embeddings_adapter()
    vectorstore = get_vectorstore_adapter()
    
    print("\n" + "="*80)
    print("RANKING PRIORITY TEST - REAL DATA")
    print("="*80)
    
    query = "how to calculate overtime pay"
    
    embedding_response = await embeddings.embed_text(query)
    query_embedding = embedding_response.embedding
    
    results = await vectorstore.query_with_chunks(
        query_embedding=query_embedding,
        limit=10,
        similarity_threshold=0.3
    )
    
    print(f"\n✓ Retrieved {len(results)} results for: '{query}'")
    print(f"\nRanking Order:")
    
    for idx, result in enumerate(results, 1):
        source_table = result.metadata.get('_source_table', 'unknown')
        score = result.score
        article = result.metadata.get('article_number', 
                 result.metadata.get('_parent_article', 'N/A'))
        
        print(f"  {idx}. [{source_table.upper():8}] {article:20} Score: {score:.3f}")
    
    print(f"\n  ✓ Ranking displayed")
    print("="*80 + "\n")


async def main():
    """Run all integration tests."""
    print("\nStarting integration tests with real ingested data...")
    print("Backend must be running with populated database")
    
    try:
        await test_ingested_documents()
        await test_deduplication()
        await test_ranking()
        print("\n✅ All integration tests completed!\n")
    except Exception as e:
        print(f"\n❌ Test suite failed: {str(e)}\n")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
