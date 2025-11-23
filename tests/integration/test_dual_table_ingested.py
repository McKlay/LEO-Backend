"""
Manual integration test for dual-table retrieval with real ingested data.

Tests with PD-851 (13th Month Pay), RA-10362 (Kasambahay Law), and COVID protocols.
Run this script with the backend running to verify dual-table retrieval works.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.containers import get_embeddings_adapter, get_vectorstore_adapter


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
            "query": "Kasambahay minimum wage",
            "expected_source": "RA-10362",
            "expect_chunks": True,
            "description": "Should retrieve RA-10362 wage-related chunks"
        },
        {
            "query": "COVID workplace protocols",
            "expected_source": "COVID",
            "expect_chunks": True,
            "description": "Should retrieve COVID protocol chunks"
        }
    ]
    
    for idx, test in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"TEST {idx}: {test['query']}")
        print(f"Expected: {test['description']}")
        print(f"{'='*80}")
        
        # Generate embedding
        try:
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
            has_sections = any(r.metadata.get('_source_table') == 'sections' for r in results)
            has_chunks = any(r.metadata.get('_source_table') == 'chunks' for r in results)
            
            print(f"  - Sections: {sum(1 for r in results if r.metadata.get('_source_table') == 'sections')}")
            print(f"  - Chunks: {sum(1 for r in results if r.metadata.get('_source_table') == 'chunks')}")
            
            # Check if expected source is present
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
                if has_chunks:
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


async def test_deduplication_real_data():
    """Test deduplication with real data."""
    
    embeddings = get_embeddings_adapter()
    vectorstore = get_vectorstore_adapter()
    
    print("\n" + "="*80)
    print("DEDUPLICATION TEST - REAL DATA")
    print("="*80)
    
    query = "13th month pay computation"
    
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
        print(f"\n  ⚠️  WARNING: Found {len(duplicates)} duplicate parent-child pairs:")
        for dup_id in list(duplicates)[:3]:
            print(f"    - {dup_id}")
    else:
        print(f"\n  ✓ PASS: No duplicate parent-child pairs found")
    
    print("="*80 + "\n")


async def test_ranking_real_data():
    """Test ranking with real data."""
    
    embeddings = get_embeddings_adapter()
    vectorstore = get_vectorstore_adapter()
    
    print("\n" + "="*80)
    print("RANKING PRIORITY TEST - REAL DATA")
    print("="*80)
    
    query = "how to calculate 13th month pay"
    
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
    
    # Verify chunks with high scores come before sections with lower scores
    violations = []
    for i in range(len(results) - 1):
        current = results[i]
        next_result = results[i + 1]
        
        current_table = current.metadata.get('_source_table')
        next_table = next_result.metadata.get('_source_table')
        
        # If current is section and next is chunk with higher score, that's wrong
        if (current_table == 'sections' and next_table == 'chunks' and 
            next_result.score > current.score + 0.05):  # Allow small margin
            violations.append((i, current, next_result))
    
    if violations:
        print(f"\n  ⚠️  Found {len(violations)} potential ranking issues")
    else:
        print(f"\n  ✓ PASS: Ranking appears correct")
    
    print("="*80 + "\n")


if __name__ == "__main__":
    print("\nStarting integration tests with real ingested data...")
    print("Ensure backend is running and database contains:")
    print("  - PD-851 (13th Month Pay)")
    print("  - RA-10362 (Kasambahay Law)")
    print("  - COVID Protocols")
    
    try:
        asyncio.run(test_ingested_documents())
        asyncio.run(test_deduplication_real_data())
        asyncio.run(test_ranking_real_data())
        print("\n✅ All integration tests completed!\n")
    except Exception as e:
        print(f"\n❌ Test suite failed: {str(e)}\n")
        import traceback
        traceback.print_exc()
