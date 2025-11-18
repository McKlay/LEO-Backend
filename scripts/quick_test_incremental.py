#!/usr/bin/env python3
"""Quick test of incremental tracking - uses COVID folder (3 files only)."""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core import get_logger
from app.containers import get_embeddings_adapter, get_vectorstore_adapter, get_llm_adapter
from kb.ingest.sync_to_vectorstore import KnowledgeBaseIngester
import psycopg2
from core.config import settings

logger = get_logger(__name__)


def delete_ingestion_history(doc_name):
    """Delete ingestion history for a document."""
    conn = psycopg2.connect(settings.supabase_db_url)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM ingestion_history WHERE file_name LIKE %s",
            (f"%{doc_name}%",)
        )
        count = cursor.rowcount
        conn.commit()
        logger.info(f"Deleted {count} history records for {doc_name}")
        return count
    finally:
        cursor.close()
        conn.close()


async def main():
    """Run quick incremental tracking test."""
    doc = "DOLE-Covid-Protocols"
    
    logger.info("="*60)
    logger.info("Quick Incremental Tracking Test")
    logger.info(f"Document: {doc} (3 files - minimal tokens)")
    logger.info("="*60 + "\n")
    
    # Step 1: Delete history
    logger.info("Step 1: Clearing history...")
    delete_ingestion_history(doc)
    await asyncio.sleep(1)
    
    # Step 2: First ingest
    logger.info("\nStep 2: First ingestion (should proceed)")
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
    
    result1 = await ingester.ingest_manual_chunks(document_name=doc, dry_run=False, force=False)
    logger.info(f"  Status: {result1['status']}")
    
    if result1['status'] != 'success':
        logger.error(f"❌ Failed to ingest: {result1.get('error')}")
        return False
    
    logger.info(f"  ✓ Ingested {result1['chunks']} chunks\n")
    
    await asyncio.sleep(1)
    
    # Step 3: Second ingest (should skip)
    logger.info("Step 3: Re-ingest without changes (should SKIP)")
    result2 = await ingester.ingest_manual_chunks(document_name=doc, dry_run=False, force=False)
    logger.info(f"  Status: {result2['status']}")
    
    if result2['status'] != 'skipped':
        logger.error(f"❌ BUG: Expected skip, got {result2['status']}")
        logger.error(f"   Reason: {result2.get('reason')}")
        logger.error("   Incremental tracking NOT working!")
        return False
    
    logger.info(f"  ✓ SKIPPED: {result2.get('reason')}\n")
    
    await asyncio.sleep(1)
    
    # Step 4: Force ingest
    logger.info("Step 4: Force re-ingest (should proceed)")
    result3 = await ingester.ingest_manual_chunks(document_name=doc, dry_run=False, force=True)
    logger.info(f"  Status: {result3['status']}")
    
    if result3['status'] != 'success':
        logger.error(f"❌ Force ingest failed")
        return False
    
    logger.info(f"  ✓ Ingested {result3['chunks']} chunks\n")
    
    await asyncio.sleep(1)
    
    # Step 5: Final skip test
    logger.info("Step 5: Final check (should SKIP again)")
    result4 = await ingester.ingest_manual_chunks(document_name=doc, dry_run=False, force=False)
    logger.info(f"  Status: {result4['status']}")
    
    if result4['status'] != 'skipped':
        logger.error(f"❌ Expected skip, got {result4['status']}")
        return False
    
    logger.info(f"  ✓ SKIPPED: {result4.get('reason')}\n")
    
    # SUCCESS
    logger.info("="*60)
    logger.info("✅ ALL TESTS PASSED!")
    logger.info("="*60)
    logger.info("Incremental tracking is WORKING correctly:")
    logger.info("  • First ingest: SUCCESS")
    logger.info("  • Unchanged re-ingest: SKIPPED ✓")
    logger.info("  • Force re-ingest: SUCCESS")
    logger.info("  • Final check: SKIPPED ✓")
    logger.info("="*60)
    
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)
