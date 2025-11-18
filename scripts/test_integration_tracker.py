#!/usr/bin/env python3
"""Quick integration test for incremental tracking with actual ingestion"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from kb.ingest.sync_to_vectorstore import KnowledgeBaseIngester
from app.containers import get_embeddings_adapter, get_vectorstore_adapter, get_llm_adapter

async def test_integration():
    """Test incremental tracking with actual ingestion (dry-run)"""
    print("\n" + "="*70)
    print("FILE-LEVEL INCREMENTAL TRACKING - INTEGRATION TEST")
    print("="*70)
    
    test_doc = "DOLE-Covid-Protocols"
    print(f"\nUsing test document: {test_doc} (3 files only)")
    
    # Initialize ingester
    embeddings = get_embeddings_adapter()
    vectorstore = get_vectorstore_adapter()
    llm = get_llm_adapter()
    
    ingester = KnowledgeBaseIngester(
        embeddings_adapter=embeddings,
        vectorstore_adapter=vectorstore,
        llm_adapter=llm,
        use_summarization=False,  # Save tokens
        use_auto_chunking=False   # Save tokens
    )
    
    print("\n--- Test 1: Initial dry-run (force) ---")
    result1 = await ingester.ingest_manual_chunks(
        document_name=test_doc,
        dry_run=True,
        force=True
    )
    print(f"Status: {result1['status']}")
    if 'chunks' in result1:
        print(f"Chunks: {result1['chunks']}")
    print(f"Reason: {result1.get('reason', 'N/A')}")
    
    if result1['status'] == 'error':
        print(f"ERROR: {result1.get('error', 'unknown')}")
        return False
    
    await asyncio.sleep(1)
    
    print("\n--- Test 2: Re-run without changes (should skip) ---")
    result2 = await ingester.ingest_manual_chunks(
        document_name=test_doc,
        dry_run=True,
        force=False
    )
    print(f"Status: {result2['status']}")
    print(f"Reason: {result2.get('reason', 'N/A')}")
    
    if result2['status'] == 'skipped':
        print("✅ PASS: Incremental tracking working - file-level skipping works!")
        return True
    elif result2['status'] == 'error':
        print(f"❌ FAIL: {result2.get('error', 'unknown')}")
        return False
    else:
        print(f"⚠️  UNEXPECTED: Status = {result2['status']}")
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(test_integration())
        print("\n" + "="*70)
        if success:
            print("✅ INTEGRATION TEST PASSED")
        else:
            print("❌ INTEGRATION TEST FAILED")
        print("="*70 + "\n")
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
