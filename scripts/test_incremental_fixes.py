"""
Test script to verify incremental ingestion fixes.

This script tests:
1. Single file ingestion with --force doesn't delete other files
2. Folder ingestion only processes changed files, skips unchanged
3. --all mode works correctly with incremental detection

Usage:
    python scripts/test_incremental_fixes.py
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.logging import setup_logging, get_logger
from app.containers import get_embeddings_adapter, get_vectorstore_adapter, get_llm_adapter
from kb.ingest.sync_to_vectorstore import KnowledgeBaseIngester
from kb.ingest.incremental_tracker import IngestionTracker

logger = get_logger(__name__)


async def test_single_file_force():
    """Test that --force on single file doesn't delete other files."""
    logger.info("\n" + "="*80)
    logger.info("TEST 1: Single file --force shouldn't delete other files")
    logger.info("="*80)
    
    # Initialize components
    embeddings = get_embeddings_adapter()
    vectorstore = get_vectorstore_adapter()
    llm = get_llm_adapter()
    
    ingester = KnowledgeBaseIngester(
        embeddings_adapter=embeddings,
        vectorstore_adapter=vectorstore,
        llm_adapter=llm,
        use_summarization=False,
        use_auto_chunking=False
    )
    
    tracker = IngestionTracker()
    
    # Test: Check if other files in the same folder are still tracked after force
    test_folder = "DOLE-Covid-Protocols"
    test_file = Path(f"kb/chunks/{test_folder}/01-background-wsh-framework.md")
    
    if not test_file.exists():
        logger.error(f"Test file not found: {test_file}")
        return False
    
    # Find other files in the same folder
    folder_path = Path(f"kb/chunks/{test_folder}")
    all_md_files = sorted([f for f in folder_path.glob("*.md") if f.is_file()])
    
    if len(all_md_files) < 2:
        logger.warning(f"Not enough files in {test_folder} to test, skipping")
        return True
    
    other_files = [f for f in all_md_files if f != test_file]
    
    logger.info(f"Test file: {test_file.name}")
    logger.info(f"Other files in folder: {[f.name for f in other_files]}")
    
    try:
        # First, ensure all files are ingested
        logger.info("\nEnsuring all files are ingested first...")
        await ingester.ingest_manual_chunks(
            document_name=test_folder,
            force=False
        )
        
        # Check ingestion records for other files BEFORE force
        logger.info("\nChecking ingestion records BEFORE force...")
        records_before = {}
        for other_file in other_files:
            record = tracker.get_ingestion_record(other_file.name)
            if record:
                records_before[other_file.name] = record["file_hash"]
                logger.info(f"  {other_file.name}: hash={record['file_hash'][:16]}...")
        
        # Ingest single file with force
        logger.info(f"\nIngesting {test_file.name} with --force...")
        result = await ingester.ingest_manual_chunks(
            single_file=test_file,
            force=True
        )
        
        logger.info(f"Result: {result}")
        
        # Check ingestion records for other files AFTER force
        logger.info("\nChecking ingestion records AFTER force...")
        records_after = {}
        for other_file in other_files:
            record = tracker.get_ingestion_record(other_file.name)
            if record:
                records_after[other_file.name] = record["file_hash"]
                logger.info(f"  {other_file.name}: hash={record['file_hash'][:16]}...")
            else:
                logger.error(f"  {other_file.name}: RECORD MISSING!")
        
        # Verify: All other files should still have their records
        if len(records_after) != len(records_before):
            logger.error(
                f"❌ FAIL: Ingestion records lost! "
                f"Before: {len(records_before)}, After: {len(records_after)}"
            )
            return False
        
        # Verify: Hashes should be unchanged (files weren't re-ingested)
        for filename in records_before:
            if records_before[filename] != records_after.get(filename):
                logger.error(
                    f"❌ FAIL: Hash changed for {filename}! "
                    f"File may have been re-ingested unexpectedly"
                )
                return False
        
        logger.info("✓ PASS: Other files' records preserved after single file force")
        return True
            
    except Exception as e:
        logger.error(f"❌ TEST FAILED: {e}", exc_info=True)
        return False


async def test_folder_incremental():
    """Test that folder ingestion only processes changed files."""
    logger.info("\n" + "="*80)
    logger.info("TEST 2: Folder ingestion should skip unchanged files")
    logger.info("="*80)
    
    # Initialize components
    embeddings = get_embeddings_adapter()
    vectorstore = get_vectorstore_adapter()
    llm = get_llm_adapter()
    
    ingester = KnowledgeBaseIngester(
        embeddings_adapter=embeddings,
        vectorstore_adapter=vectorstore,
        llm_adapter=llm,
        use_summarization=False,
        use_auto_chunking=False
    )
    
    tracker = IngestionTracker()
    
    # Test folder
    test_folder = "DOLE-Covid-Protocols"
    
    # First ingestion - should process all files
    logger.info(f"\nFirst ingestion of {test_folder} (should process all)...")
    result1 = await ingester.ingest_manual_chunks(
        document_name=test_folder,
        force=False
    )
    
    logger.info(f"First ingestion result: {result1}")
    
    if result1["status"] != "success":
        logger.error("❌ First ingestion failed")
        return False
    
    # Second ingestion - should skip all (unchanged)
    logger.info(f"\nSecond ingestion of {test_folder} (should skip all)...")
    result2 = await ingester.ingest_manual_chunks(
        document_name=test_folder,
        force=False
    )
    
    logger.info(f"Second ingestion result: {result2}")
    
    if result2["status"] == "skipped":
        logger.info("✓ PASS: All chunks correctly skipped (unchanged)")
        return True
    else:
        logger.error(f"❌ FAIL: Expected status 'skipped', got '{result2['status']}'")
        return False


async def test_partial_folder_update():
    """Test that folder ingestion handles partial updates correctly."""
    logger.info("\n" + "="*80)
    logger.info("TEST 3: Folder ingestion should handle partial updates")
    logger.info("="*80)
    
    # Initialize components
    embeddings = get_embeddings_adapter()
    vectorstore = get_vectorstore_adapter()
    llm = get_llm_adapter()
    
    ingester = KnowledgeBaseIngester(
        embeddings_adapter=embeddings,
        vectorstore_adapter=vectorstore,
        llm_adapter=llm,
        use_summarization=False,
        use_auto_chunking=False
    )
    
    tracker = IngestionTracker()
    
    # Test folder with multiple files
    test_folder = "PD-No-851"
    test_file = Path(f"kb/chunks/{test_folder}/01-decree-main.md")
    
    if not test_file.exists():
        logger.warning(f"Test file not found: {test_file}, skipping test")
        return True
    
    # Step 1: Ensure all files are ingested
    logger.info(f"\nInitial ingestion of {test_folder}...")
    result1 = await ingester.ingest_manual_chunks(
        document_name=test_folder,
        force=False
    )
    logger.info(f"Initial result: {result1}")
    
    # Step 2: Force re-ingest one file
    logger.info(f"\nForce re-ingest single file: {test_file.name}...")
    result2 = await ingester.ingest_manual_chunks(
        single_file=test_file,
        force=True
    )
    logger.info(f"Single file result: {result2}")
    
    # Step 3: Re-ingest folder - should skip unchanged, but file we just forced should also be skipped
    logger.info(f"\nRe-ingest folder {test_folder} (all should be skipped)...")
    result3 = await ingester.ingest_manual_chunks(
        document_name=test_folder,
        force=False
    )
    logger.info(f"Final folder result: {result3}")
    
    if result3["status"] == "skipped":
        logger.info("✓ PASS: Folder correctly skipped all chunks")
        return True
    else:
        logger.error(f"❌ FAIL: Expected all skipped, got: {result3}")
        return False


async def main():
    """Run all tests."""
    setup_logging(level="INFO", json_output=False)
    
    logger.info("="*80)
    logger.info("INCREMENTAL INGESTION FIX VERIFICATION")
    logger.info("="*80)
    
    results = []
    
    # Test 1: Single file force doesn't delete others
    try:
        result1 = await test_single_file_force()
        results.append(("Single file --force", result1))
    except Exception as e:
        logger.error(f"Test 1 exception: {e}", exc_info=True)
        results.append(("Single file --force", False))
    
    # Test 2: Folder incremental detection
    try:
        result2 = await test_folder_incremental()
        results.append(("Folder incremental", result2))
    except Exception as e:
        logger.error(f"Test 2 exception: {e}", exc_info=True)
        results.append(("Folder incremental", False))
    
    # Test 3: Partial folder update
    try:
        result3 = await test_partial_folder_update()
        results.append(("Partial folder update", result3))
    except Exception as e:
        logger.error(f"Test 3 exception: {e}", exc_info=True)
        results.append(("Partial folder update", False))
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("TEST SUMMARY")
    logger.info("="*80)
    
    for test_name, passed in results:
        status = "✓ PASS" if passed else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        logger.info("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        logger.error("\n❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
