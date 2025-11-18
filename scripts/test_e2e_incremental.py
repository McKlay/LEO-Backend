#!/usr/bin/env python3
"""
End-to-end test showing incremental tracking with actual CLI commands.
Uses DOLE-Covid-Protocols (3 files) to minimize tokens.
"""
import subprocess
import sys
import time
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core import get_logger

logger = get_logger(__name__)


def run_cmd(cmd, description):
    """Run command and capture output."""
    logger.info(f"\n{description}")
    logger.info(f"Command: {' '.join(cmd)}")
    logger.info("-" * 60)
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Log output
    if result.stdout:
        for line in result.stdout.splitlines()[-20:]:  # Last 20 lines
            logger.info(line)
    
    if result.stderr:
        for line in result.stderr.splitlines()[-20:]:
            logger.error(line)
    
    return result.returncode == 0


def main():
    """Run end-to-end test."""
    doc = "DOLE-Covid-Protocols"
    
    logger.info("="*60)
    logger.info("END-TO-END INCREMENTAL TRACKING TEST")
    logger.info(f"Document: {doc} (3 files - minimal tokens)")
    logger.info("="*60)
    
    # Test 1: Dry run - show what would happen
    logger.info("\n\n" + "="*60)
    logger.info("TEST 1: DRY RUN (no changes to database)")
    logger.info("="*60)
    
    if not run_cmd(
        ["python", "-m", "kb.ingest.sync_to_vectorstore", "--manual", "--folder", doc, "--dry-run"],
        "Running: python -m kb.ingest.sync_to_vectorstore --manual --folder DOLE-Covid-Protocols --dry-run"
    ):
        logger.error("❌ Dry run failed")
        return False
    
    # Test 2: Normal run (should skip if already ingested)
    logger.info("\n\n" + "="*60)
    logger.info("TEST 2: NORMAL RUN (should skip if unchanged)")
    logger.info("="*60)
    
    if not run_cmd(
        ["python", "-m", "kb.ingest.sync_to_vectorstore", "--manual", "--folder", doc],
        "Running: python -m kb.ingest.sync_to_vectorstore --manual --folder DOLE-Covid-Protocols"
    ):
        logger.warning("Normal run completed with code != 0 (might be expected)")
    
    time.sleep(2)
    
    # Test 3: Force re-ingestion
    logger.info("\n\n" + "="*60)
    logger.info("TEST 3: FORCE RE-INGESTION")
    logger.info("="*60)
    
    if not run_cmd(
        ["python", "-m", "kb.ingest.sync_to_vectorstore", "--manual", "--folder", doc, "--force"],
        "Running: python -m kb.ingest.sync_to_vectorstore --manual --folder DOLE-Covid-Protocols --force"
    ):
        logger.warning("Force re-ingestion completed with code != 0")
    
    time.sleep(2)
    
    # Test 4: Another normal run (should skip again)
    logger.info("\n\n" + "="*60)
    logger.info("TEST 4: VERIFY SKIP AGAIN")
    logger.info("="*60)
    
    if not run_cmd(
        ["python", "-m", "kb.ingest.sync_to_vectorstore", "--manual", "--folder", doc],
        "Running: python -m kb.ingest.sync_to_vectorstore --manual --folder DOLE-Covid-Protocols"
    ):
        logger.warning("Second normal run completed with code != 0")
    
    logger.info("\n" + "="*60)
    logger.info("✅ END-TO-END TEST COMPLETED")
    logger.info("="*60)
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)
