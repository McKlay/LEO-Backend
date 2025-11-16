"""
Add a new source manually to the database.

Usage:
    python scripts/database_ingestion/add_source.py \\
        --name "DOLE Department Order No. 174" \\
        --type "department_order" \\
        --reference "DO-174" \\
        --description "Guidelines on the Implementation of Flexible Work Arrangements"
"""
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from kb.ingest.source_manager import SourceManager
from core import get_logger
from core.logging import setup_logging

setup_logging(level="INFO", json_output=False)
logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Add a new source to the database")
    parser.add_argument(
        "--name",
        type=str,
        required=True,
        help="Source name (e.g., 'Labor Code of the Philippines')"
    )
    parser.add_argument(
        "--type",
        type=str,
        required=True,
        choices=[
            "labor_code",
            "presidential_decree",
            "republic_act",
            "department_order",
            "issuance",
            "handbook"
        ],
        help="Source type"
    )
    parser.add_argument(
        "--reference",
        type=str,
        required=True,
        help="Reference code (e.g., 'PD-442', 'RA-11058', 'DO-174')"
    )
    parser.add_argument(
        "--description",
        type=str,
        help="Description of the source"
    )
    parser.add_argument(
        "--effective-date",
        type=str,
        help="Effective date (YYYY-MM-DD format)"
    )
    parser.add_argument(
        "--issuing-authority",
        type=str,
        help="Issuing authority (e.g., 'DOLE', 'Congress')"
    )
    parser.add_argument(
        "--url",
        type=str,
        help="Official URL"
    )
    
    args = parser.parse_args()
    
    # Build metadata
    metadata = {
        "description": args.description,
    }
    
    if args.effective_date:
        try:
            datetime.strptime(args.effective_date, "%Y-%m-%d")
            metadata["effective_date"] = args.effective_date
        except ValueError:
            logger.error("Invalid date format. Use YYYY-MM-DD")
            return 1
    
    if args.issuing_authority:
        metadata["issuing_authority"] = args.issuing_authority
    
    if args.url:
        metadata["url"] = args.url
    
    # Add source
    logger.info(f"\nAdding source: {args.name}")
    logger.info(f"Type: {args.type}")
    logger.info(f"Reference: {args.reference}")
    
    source_manager = SourceManager()
    
    try:
        source_id = source_manager.create_source(
            name=args.name,
            source_type=args.type,
            reference_code=args.reference,
            metadata=metadata
        )
        
        logger.info(f"\n✅ Source created successfully!")
        logger.info(f"Source ID: {source_id}")
        logger.info(f"\nNext steps:")
        logger.info(f"1. Place the document file in: kb/docs/")
        logger.info(f"2. Add entry to DOCUMENT_REGISTRY in kb/ingest/registry.py")
        logger.info(f"3. Run ingestion: python scripts/database_ingestion/ingest_single.py --file <filename>")
        
        return 0
    
    except Exception as e:
        logger.error(f"\n❌ Failed to create source: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
