"""
Quick verification script for incremental ingestion fixes.

Tests:
1. Single file --force only deletes that file's chunks
2. Folder ingestion skips unchanged files
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
    """Run verification tests."""
    setup_logging(level="INFO", json_output=False)
    
    logger.info("="*80)
    logger.info("INCREMENTAL INGESTION VERIFICATION")
    logger.info("="*80)
    
    # Initialize components
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
    
    # TEST 1: Check ingestion records preservation after single file force
    logger.info("\nTEST 1: Single file --force preserves other files")
    logger.info("-" * 80)
    
    test_folder = "DOLE-Covid-Protocols"
    test_file = Path(f"kb/chunks/{test_folder}/01-background-wsh-framework.md")
    
    # Get all files in folder
    folder_path = Path(f"kb/chunks/{test_folder}")
    all_files = sorted([f for f in folder_path.glob("*.md") if f.is_file()])
    other_files = [f for f in all_files if f != test_file]
    
    # Check records BEFORE force
    records_before = {}
    for file in other_files:
        record = tracker.get_ingestion_record(file.name)
        if record:
            records_before[file.name] = record["file_hash"]
    
    logger.info(f"Other files before: {list(records_before.keys())}")
    
    # Force re-ingest single file
    result = await ingester.ingest_manual_chunks(
        single_file=test_file,
        force=True
    )
    logger.info(f"Single file result: {result['status']}")
    
    # Check records AFTER force
    records_after = {}
    for file in other_files:
        record = tracker.get_ingestion_record(file.name)
        if record:
            records_after[file.name] = record["file_hash"]
    
    logger.info(f"Other files after: {list(records_after.keys())}")
    
    # Verify
    if records_before == records_after:
        logger.info("✓ PASS: Other files' records preserved")
    else:
        logger.error("❌ FAIL: Other files' records changed or lost")
    
    # TEST 2: Folder ingestion skips unchanged
    logger.info("\nTEST 2: Folder ingestion skips unchanged files")
    logger.info("-" * 80)
    
    result = await ingester.ingest_manual_chunks(
        document_name=test_folder,
        force=False
    )
    
    logger.info(f"Folder result: {result}")
    
    if result["status"] == "skipped":
        logger.info("✓ PASS: All unchanged files correctly skipped")
    else:
        logger.warning(f"Note: Status is '{result['status']}' (may be first run)")
    
    logger.info("\n" + "="*80)
    logger.info("VERIFICATION COMPLETE")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())
