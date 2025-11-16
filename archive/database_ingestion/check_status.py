"""
Check status of a specific file ingestion.

Usage:
    python scripts/database_ingestion/check_status.py --file PD-851.txt
    python scripts/database_ingestion/check_status.py --file DOLE-Handbook.txt
"""
import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from kb.ingest.incremental_tracker import IngestionTracker
from core import get_logger
from core.logging import setup_logging

setup_logging(level="INFO", json_output=False)
logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Check file ingestion status")
    parser.add_argument(
        "--file",
        type=str,
        required=True,
        help="Filename to check (e.g., PD-851.txt)"
    )
    
    args = parser.parse_args()
    
    tracker = IngestionTracker()
    
    # Get ingestion record
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from core.config import settings
    
    conn = psycopg2.connect(settings.supabase_db_url)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM ingestion_history
        WHERE file_name = %s
        ORDER BY created_at DESC
        LIMIT 1
    """, (args.file,))
    
    record = cur.fetchone()
    
    if not record:
        logger.warning(f"No ingestion record found for: {args.file}")
        logger.info("\nFile has not been ingested yet.")
        cur.close()
        conn.close()
        return 1
    
    # Get section count
    cur.execute("""
        SELECT COUNT(*) as count
        FROM labor_law_sections
        WHERE metadata->>'source' LIKE %s
    """, (f"%{args.file.replace('.txt', '')}%",))
    
    section_count = cur.fetchone()['count']
    
    cur.close()
    conn.close()
    
    # Display status
    logger.info(f"\n{'='*60}")
    logger.info(f"FILE INGESTION STATUS: {args.file}")
    logger.info(f"{'='*60}\n")
    
    status_symbol = {
        "success": "✅",
        "failed": "❌",
        "in_progress": "⏳"
    }.get(record['status'], "❓")
    
    logger.info(f"Status: {status_symbol} {record['status'].upper()}")
    logger.info(f"Method: {record.get('ingestion_method', 'N/A')}")
    logger.info(f"Chunks Created: {record.get('chunk_count', 0)}")
    logger.info(f"Chunks in DB: {section_count}")
    logger.info(f"Tokens Used: {record.get('token_count', 0)}")
    logger.info(f"File Hash: {record.get('file_hash', 'N/A')[:16]}...")
    logger.info(f"Ingested: {record.get('created_at', 'N/A')}")
    
    if record.get('error_message'):
        logger.error(f"\nError: {record['error_message']}")
    
    logger.info(f"\n{'='*60}\n")
    
    if record['status'] == 'success':
        logger.info("✅ Ingestion successful")
        return 0
    else:
        logger.error("❌ Ingestion had issues")
        return 1


if __name__ == "__main__":
    sys.exit(main())
