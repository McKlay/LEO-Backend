"""
Check ingestion history.

Usage:
    python scripts/database_ingestion/check_history.py
    python scripts/database_ingestion/check_history.py --last 10
    python scripts/database_ingestion/check_history.py --status failed
    python scripts/database_ingestion/check_history.py --file PD-851.txt
"""
import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core import get_logger
from core.logging import setup_logging
from core.config import settings
import psycopg2
from psycopg2.extras import RealDictCursor

setup_logging(level="INFO", json_output=False)
logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Check ingestion history")
    parser.add_argument(
        "--last",
        "--limit",
        type=int,
        default=20,
        help="Number of recent records to show (default: 20)"
    )
    parser.add_argument(
        "--status",
        choices=["success", "failed", "in_progress"],
        help="Filter by status"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Filter by filename"
    )
    
    args = parser.parse_args()
    
    conn = psycopg2.connect(settings.supabase_db_url)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Build query
    query = "SELECT * FROM ingestion_history WHERE 1=1"
    params = []
    
    if args.status:
        query += " AND status = %s"
        params.append(args.status)
    
    if args.file:
        query += " AND file_name = %s"
        params.append(args.file)
    
    query += " ORDER BY created_at DESC LIMIT %s"
    params.append(args.last)
    
    cur.execute(query, params)
    records = cur.fetchall()
    
    cur.close()
    conn.close()
    
    logger.info(f"\n{'='*80}")
    logger.info(f"INGESTION HISTORY ({len(records)} records)")
    logger.info(f"{'='*80}\n")
    
    if not records:
        logger.info("No records found")
        return 0
    
    for record in records:
        status_symbol = {
            "success": "✓",
            "failed": "✗",
            "in_progress": "⏳"
        }.get(record['status'], "?")
        
        logger.info(f"{status_symbol} {record['file_name']}")
        logger.info(f"  Status: {record['status']}")
        logger.info(f"  Method: {record.get('ingestion_method', 'N/A')}")
        logger.info(f"  Chunks: {record.get('chunk_count', 0)}")
        logger.info(f"  Tokens: {record.get('token_count', 0)}")
        logger.info(f"  Date: {record.get('created_at', 'N/A')}")
        
        if record.get('error_message'):
            logger.info(f"  Error: {record['error_message']}")
        
        logger.info(f"{'-'*80}\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
