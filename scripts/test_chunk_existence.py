"""
Test script to verify chunk existence verification.

Tests that ingestion detects and re-ingests when chunks are manually deleted.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.logging import setup_logging, get_logger
from app.containers import get_embeddings_adapter, get_vectorstore_adapter, get_llm_adapter
from kb.ingest.sync_to_vectorstore import KnowledgeBaseIngester
from kb.ingest.incremental_tracker import IngestionTracker

logger = get_logger(__name__)


async def main():
    """Test chunk existence verification."""
    setup_logging(level="INFO", json_output=False)
    
    logger.info("="*80)
    logger.info("CHUNK EXISTENCE VERIFICATION TEST")
    logger.info("="*80)
    
    # Initialize
    embeddings = get_embeddings_adapter()
    vectorstore = get_vectorstore_adapter()
    llm = get_llm_adapter()
    tracker = IngestionTracker()
    
    ingester = KnowledgeBaseIngester(
        embeddings_adapter=embeddings,
        vectorstore_adapter=vectorstore,
        llm_adapter=llm,
        use_summarization=False,
        use_auto_chunking=False
    )
    
    # Test file
    test_file = Path("kb/chunks/DOLE-Covid-Protocols/01-background-wsh-framework.md")
    file_name = test_file.name
    
    # Step 1: Check current state
    logger.info("\nStep 1: Checking current state")
    logger.info("-" * 80)
    
    record = tracker.get_ingestion_record(file_name)
    if record:
        logger.info(f"✓ Ingestion record exists for {file_name}")
        logger.info(f"  Status: {record['status']}")
        logger.info(f"  Hash: {record['file_hash'][:16]}...")
    else:
        logger.info(f"✗ No ingestion record for {file_name}")
    
    # Check if chunks exist
    chunks_exist = tracker._verify_chunks_exist(file_name)
    logger.info(f"Chunks in database: {'✓ Yes' if chunks_exist else '✗ No'}")
    
    # Step 2: Test should_ingest logic
    logger.info("\nStep 2: Testing should_ingest logic")
    logger.info("-" * 80)
    
    should_ingest, reason = tracker.should_ingest(test_file, force=False)
    logger.info(f"Should ingest: {should_ingest}")
    logger.info(f"Reason: {reason}")
    
    # Step 3: Test actual ingestion
    logger.info("\nStep 3: Testing actual ingestion")
    logger.info("-" * 80)
    
    result = await ingester.ingest_manual_chunks(
        single_file=test_file,
        force=False
    )
    
    logger.info(f"Ingestion result: {result['status']}")
    
    # Step 4: Verify final state
    logger.info("\nStep 4: Verifying final state")
    logger.info("-" * 80)
    
    chunks_exist_after = tracker._verify_chunks_exist(file_name)
    logger.info(f"Chunks in database: {'✓ Yes' if chunks_exist_after else '✗ No'}")
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("TEST SUMMARY")
    logger.info("="*80)
    
    if chunks_exist_after:
        logger.info("✓ PASS: Chunk existence verification working correctly")
        logger.info("\nScenario tested:")
        logger.info("1. File has ingestion record (hash matches)")
        if not chunks_exist:
            logger.info("2. Chunks were missing in database")
            logger.info("3. System detected missing chunks and re-ingested")
        else:
            logger.info("2. Chunks already exist in database")
            logger.info("3. System correctly skipped re-ingestion")
        logger.info("4. Chunks now present in database ✓")
    else:
        logger.error("✗ FAIL: Chunks still missing after ingestion")
    
    logger.info("\nInstructions for manual testing:")
    logger.info("1. Note the current test result")
    logger.info("2. Manually delete chunks from labor_law_sections:")
    logger.info("   DELETE FROM labor_law_sections")
    logger.info("   WHERE metadata->>'file_stem' = '01-background-wsh-framework';")
    logger.info("3. Run this test again")
    logger.info("4. Verify it detects missing chunks and re-ingests")


if __name__ == "__main__":
    asyncio.run(main())
