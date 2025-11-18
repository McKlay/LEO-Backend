#!/usr/bin/env python3
"""Diagnostic: Test the incremental tracker directly."""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core import get_logger
from kb.ingest.incremental_tracker import IngestionTracker

logger = get_logger(__name__)

# Test the tracker directly
tracker = IngestionTracker()

doc_folder = Path("kb/chunks/DOLE-Covid-Protocols")

logger.info("="*60)
logger.info("Testing IngestionTracker directly")
logger.info("="*60)

logger.info(f"\nFolder: {doc_folder}")
logger.info(f"Exists: {doc_folder.exists()}")

# Calculate hash
logger.info("\nCalculating folder hash...")
try:
    folder_hash = tracker.calculate_folder_hash(doc_folder)
    logger.info(f"✓ Hash: {folder_hash[:16]}...")
except Exception as e:
    logger.error(f"❌ Error: {e}")
    sys.exit(1)

# Get ingestion record
logger.info("\nGetting ingestion record...")
record = tracker.get_ingestion_record("DOLE-Covid-Protocols")
if record:
    logger.info(f"✓ Found record:")
    logger.info(f"  Status: {record['status']}")
    logger.info(f"  Hash: {record['file_hash'][:16]}...")
    logger.info(f"  Chunks: {record['chunk_count']}")
    logger.info(f"  Method: {record['ingestion_method']}")
else:
    logger.info("✗ No record found")

# Test should_ingest
logger.info("\nTesting should_ingest()...")
should_ingest, reason = tracker.should_ingest(
    Path("kb/chunks/DOLE-Covid-Protocols"),
    force=False
)
logger.info(f"  Should ingest: {should_ingest}")
logger.info(f"  Reason: {reason}")

logger.info("\n" + "="*60)
if not should_ingest:
    logger.info("✅ Incremental tracking is WORKING!")
    logger.info(f"   Document will be SKIPPED: {reason}")
else:
    logger.info("❌ Incremental tracking NOT WORKING!")
    logger.info(f"   Document will be RE-INGESTED: {reason}")
logger.info("="*60)
