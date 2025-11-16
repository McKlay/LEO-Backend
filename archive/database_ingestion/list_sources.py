"""
List all sources in the database.

Usage:
    python scripts/database_ingestion/list_sources.py
    python scripts/database_ingestion/list_sources.py --filter "COVID"
    python scripts/database_ingestion/list_sources.py --format json
"""
import sys
import argparse
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from kb.ingest.source_manager import SourceManager
from core import get_logger
from core.logging import setup_logging

setup_logging(level="INFO", json_output=False)
logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description="List all labor law sources")
    parser.add_argument(
        "--filter",
        type=str,
        help="Filter sources by reference or title (case-insensitive)"
    )
    parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format"
    )
    
    args = parser.parse_args()
    
    manager = SourceManager()
    sources = manager.list_all_sources()
    
    # Apply filter
    if args.filter:
        filter_lower = args.filter.lower()
        sources = [
            s for s in sources
            if filter_lower in s['reference'].lower() or filter_lower in s['title'].lower()
        ]
    
    if args.format == "json":
        print(json.dumps(sources, indent=2, default=str))
    else:
        logger.info(f"\n{'='*80}")
        logger.info(f"LABOR LAW SOURCES ({len(sources)} total)")
        logger.info(f"{'='*80}\n")
        
        for source in sources:
            logger.info(f"Reference: {source['reference']}")
            logger.info(f"Title: {source['title']}")
            logger.info(f"Type: {source['source_type']}")
            logger.info(f"Sections: {source.get('section_count', 0)}")
            logger.info(f"ID: {source['id']}")
            logger.info(f"URL: {source.get('url', 'N/A')}")
            logger.info(f"{'-'*80}\n")


if __name__ == "__main__":
    main()
