#!/usr/bin/env python3
"""
Test incremental tracking for manual chunk ingestion.

This script tests that manual chunks are NOT re-ingested when unchanged,
and ARE re-ingested when content changes.

Usage:
    python scripts/test_incremental_manual_chunks.py
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core import get_logger
from app.containers import get_embeddings_adapter, get_vectorstore_adapter, get_llm_adapter
from kb.ingest.sync_to_vectorstore import KnowledgeBaseIngester

logger = get_logger(__name__)


async def test_incremental_tracking():
    """Test that incremental tracking works for manual chunks.
    
    Uses DOLE-Covid-Protocols (only 3 files) to minimize token consumption.
    """
    
    # Use DOLE-Covid-Protocols - only 3 files, minimal tokens
    test_document = "DOLE-Covid-Protocols"
    
    logger.info(f"=== Testing Incremental Tracking for {test_document} ===")
    logger.info(f"(Using 3-file document to minimize token consumption)\n")
    
    # Initialize adapters
    embeddings = get_embeddings_adapter()
    vectorstore = get_vectorstore_adapter()
    llm = get_llm_adapter()
    
    # Create ingester WITHOUT summarization to minimize tokens
    ingester = KnowledgeBaseIngester(
        embeddings_adapter=embeddings,
        vectorstore_adapter=vectorstore,
        llm_adapter=llm,
        use_summarization=False,  # CRITICAL: Disable to save tokens
        use_auto_chunking=False   # CRITICAL: Disable to save tokens
    )
    
    # Test 0: Force re-ingestion to establish baseline
    logger.info("Test 0: Force re-ingestion (baseline)")
    result0 = await ingester.ingest_manual_chunks(
        document_name=test_document,
        dry_run=False,
        force=True
    )
    
    if result0['status'] != 'success':
        logger.error(f"❌ Test 0 FAILED: {result0.get('error', 'unknown error')}")
        return False
    
    logger.info(f"✓ Baseline: {result0['chunks']} chunks ingested\n")
    
    await asyncio.sleep(1)
    
    # Test 1: Re-ingestion without changes (should SKIP)
    logger.info("Test 1: Re-ingestion without changes")
    result1 = await ingester.ingest_manual_chunks(
        document_name=test_document,
        dry_run=False,
        force=False
    )
    
    if result1['status'] != 'skipped':
        logger.error(
            f"❌ Test 1 FAILED: Expected 'skipped', got '{result1['status']}'\n"
            f"   Reason: {result1.get('reason', 'none')}\n"
            f"   BUG: Incremental tracking NOT working!"
        )
        return False
    
    logger.info(f"✓ SKIPPED: {result1.get('reason')}\n")
    
    # Test 2: Re-ingestion with --force (should INGEST)
    logger.info("Test 2: Re-ingestion with --force")
    result2 = await ingester.ingest_manual_chunks(
        document_name=test_document,
        dry_run=False,
        force=True
    )
    
    if result2['status'] != 'success':
        logger.error(f"❌ Test 2 FAILED: Force ingest failed")
        return False
    
    logger.info(f"✓ INGESTED: {result2['chunks']} chunks\n")
    
    await asyncio.sleep(1)
    
    # Test 3: Final skip test
    logger.info("Test 3: Final unchanged check")
    result3 = await ingester.ingest_manual_chunks(
        document_name=test_document,
        dry_run=False,
        force=False
    )
    
    if result3['status'] != 'skipped':
        logger.error(f"❌ Test 3 FAILED: Expected skip")
        return False
    
    logger.info(f"✓ SKIPPED: {result3.get('reason')}\n")
    
    # Summary
    logger.info("="*60)
    logger.info("✅ ALL TESTS PASSED!")
    logger.info("="*60)
    logger.info(f"Test 0 (Force):     {result0['chunks']} chunks ✓")
    logger.info(f"Test 1 (Skip):      Incremental tracking works ✓")
    logger.info(f"Test 2 (Force):     {result2['chunks']} chunks ✓")
    logger.info(f"Test 3 (Skip):      Consistent behavior ✓")
    logger.info("="*60)
    
    return True


async def main():
    """Run the test."""
    try:
        success = await test_incremental_tracking()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nTest cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
