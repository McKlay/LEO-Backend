"""
Batch ingestion of all labor law documents.

Usage:
    python scripts/database_ingestion/ingest_all.py
    python scripts/database_ingestion/ingest_all.py --dry-run
    python scripts/database_ingestion/ingest_all.py --force
    python scripts/database_ingestion/ingest_all.py --new-only
    python scripts/database_ingestion/ingest_all.py --use-regex
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import from original location
from scripts.ingest_all_kb import main

if __name__ == "__main__":
    main()
