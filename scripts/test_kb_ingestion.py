"""
Test script for knowledge base ingestion.

Tests the complete ingestion pipeline:
1. Document loading
2. Chunking
3. Embedding generation
4. Vector store upsert
5. Retrieval verification
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core import get_logger
from app.containers import get_embeddings_adapter, get_vectorstore_adapter
from retrieval.chunking import LegalDocumentChunker
from kb.ingest.loaders import TextFileLoader
from kb.ingest.sync_to_vectorstore import KnowledgeBaseIngester

logger = get_logger(__name__)


async def test_text_loader():
    """Test text file loading."""
    print("\n" + "="*60)
    print("TEST 1: Text File Loading")
    print("="*60)
    
    loader = TextFileLoader()
    test_file = Path("kb/docs/PD-No-442.txt")
    
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return False
    
    try:
        content = loader.load(test_file)
        word_count = len(content.split())
        
        print(f"✓ Loaded {test_file.name}")
        print(f"  - Characters: {len(content):,}")
        print(f"  - Words: {word_count:,}")
        print(f"  - Preview: {content[:200]}...")
        
        return True
    except Exception as e:
        print(f"❌ Failed to load file: {str(e)}")
        return False


async def test_chunking():
    """Test document chunking."""
    print("\n" + "="*60)
    print("TEST 2: Document Chunking")
    print("="*60)
    
    loader = TextFileLoader()
    chunker = LegalDocumentChunker(
        min_chunk_words=100,
        max_chunk_words=300,
        overlap_words=20
    )
    
    test_file = Path("kb/docs/PD-No-851.txt")  # Smaller file for testing
    
    if not test_file.exists():
        test_file = Path("kb/docs/PD-No-442.txt")
    
    try:
        content = loader.load(test_file)
        
        chunks = chunker.chunk_document(
            content=content,
            source="Test Document",
            doc_type="statute",
            base_url="https://lawphil.net/test"
        )
        
        print(f"✓ Created {len(chunks)} chunks from {test_file.name}")
        print(f"\nFirst chunk sample:")
        print(f"  ID: {chunks[0].id}")
        print(f"  Words: {chunks[0].word_count}")
        print(f"  Metadata: {chunks[0].metadata}")
        print(f"  Content preview: {chunks[0].content[:150]}...")
        
        if len(chunks) > 1:
            print(f"\nLast chunk sample:")
            print(f"  ID: {chunks[-1].id}")
            print(f"  Words: {chunks[-1].word_count}")
        
        return True
    except Exception as e:
        print(f"❌ Chunking failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_embeddings():
    """Test embedding generation."""
    print("\n" + "="*60)
    print("TEST 3: Embedding Generation")
    print("="*60)
    
    try:
        embeddings = get_embeddings_adapter()
        
        test_text = "The employer shall pay every employee a 13th month pay."
        
        print(f"Generating embedding for: '{test_text}'")
        
        response = await embeddings.embed_text(test_text)
        
        print(f"✓ Embedding generated")
        print(f"  - Model: {response.model}")
        print(f"  - Tokens used: {response.tokens_used}")
        print(f"  - Embedding dimension: {len(response.embedding)}")
        print(f"  - First 5 values: {response.embedding[:5]}")
        
        return True
    except Exception as e:
        print(f"❌ Embedding generation failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_dry_run_ingestion():
    """Test ingestion in dry-run mode."""
    print("\n" + "="*60)
    print("TEST 4: Dry-Run Ingestion")
    print("="*60)
    
    try:
        embeddings = get_embeddings_adapter()
        vectorstore = get_vectorstore_adapter()
        
        ingester = KnowledgeBaseIngester(
            embeddings_adapter=embeddings,
            vectorstore_adapter=vectorstore
        )
        
        test_file = Path("kb/docs/PD-No-851.txt")
        
        if not test_file.exists():
            print(f"❌ Test file not found: {test_file}")
            return False
        
        result = await ingester.ingest_file(test_file, dry_run=True)
        
        print(f"✓ Dry-run completed")
        print(f"  - File: {result['file']}")
        print(f"  - Chunks: {result['chunks']}")
        print(f"  - Status: {result['status']}")
        
        return True
    except Exception as e:
        print(f"❌ Dry-run ingestion failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_full_ingestion():
    """Test full ingestion with vector store."""
    print("\n" + "="*60)
    print("TEST 5: Full Ingestion (1 file)")
    print("="*60)
    
    try:
        embeddings = get_embeddings_adapter()
        vectorstore = get_vectorstore_adapter()
        
        ingester = KnowledgeBaseIngester(
            embeddings_adapter=embeddings,
            vectorstore_adapter=vectorstore
        )
        
        # Use smaller file for faster testing
        test_file = Path("kb/docs/PD-No-851.txt")
        
        if not test_file.exists():
            print(f"⚠️  PD-No-851.txt not found, skipping full ingestion test")
            return True  # Don't fail if file missing
        
        print("⚠️  This will actually insert data into Supabase!")
        print("Press Ctrl+C to cancel...")
        await asyncio.sleep(2)
        
        result = await ingester.ingest_file(test_file, dry_run=False)
        
        if result['status'] == 'success':
            print(f"✓ Ingestion completed successfully")
            print(f"  - File: {result['file']}")
            print(f"  - Chunks: {result['chunks']}")
            print(f"  - Tokens: {result['tokens']}")
            return True
        else:
            print(f"❌ Ingestion failed: {result.get('error', 'Unknown error')}")
            return False
            
    except KeyboardInterrupt:
        print("\n⚠️  Test cancelled by user")
        return True
    except Exception as e:
        print(f"❌ Full ingestion failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_retrieval():
    """Test retrieval from vector store."""
    print("\n" + "="*60)
    print("TEST 6: Vector Store Retrieval")
    print("="*60)
    
    try:
        embeddings = get_embeddings_adapter()
        vectorstore = get_vectorstore_adapter()
        
        # First, check if we have any data
        print("Checking database...")
        from app.containers import get_supabase_client
        client = get_supabase_client()
        count_result = client.table("labor_law_embeddings").select("id", count="exact").execute()
        print(f"Total documents in database: {count_result.count}")
        
        if count_result.count == 0:
            print("⚠️  No documents in database yet. Run ingestion first.")
            return False
        
        # Generate query embedding
        query = "What is the 13th month pay?"
        print(f"Query: '{query}'")
        
        response = await embeddings.embed_text(query)
        query_embedding = response.embedding
        
        # Search vector store with lower threshold
        results = await vectorstore.query(
            query_embedding=query_embedding,
            limit=3,
            threshold=0.0  # Lower threshold for testing
        )
        
        print(f"\n✓ Retrieved {len(results)} results")
        
        for i, result in enumerate(results, 1):
            print(f"\nResult {i}:")
            print(f"  - ID: {result.id}")
            print(f"  - Score: {result.score:.4f}")
            print(f"  - Source: {result.metadata.get('source', 'Unknown')}")
            print(f"  - Article: {result.metadata.get('article', 'N/A')}")
            print(f"  - Content: {result.content[:150]}...")
        
        return len(results) > 0
        
    except Exception as e:
        print(f"❌ Retrieval failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("KNOWLEDGE BASE INGESTION TEST SUITE")
    print("="*60)
    
    tests = [
        ("Text Loading", test_text_loader),
        ("Document Chunking", test_chunking),
        ("Embedding Generation", test_embeddings),
        ("Dry-Run Ingestion", test_dry_run_ingestion),
        ("Full Ingestion", test_full_ingestion),
        ("Vector Retrieval", test_retrieval),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {str(e)}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"{status:8} {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nTests cancelled by user")
        sys.exit(130)
