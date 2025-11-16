"""
Ingest a single labor law document.

Usage:
    python scripts/database_ingestion/ingest_single.py --file kb/docs/PD-No-851.txt
    python scripts/database_ingestion/ingest_single.py --file kb/docs/PD-No-442.txt --dry-run
    python scripts/database_ingestion/ingest_single.py --file kb/docs/PD-No-442.txt --force
    python scripts/database_ingestion/ingest_single.py --file kb/docs/PD-No-442.txt --use-regex
"""
import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import from original CLI
from kb.ingest.sync_to_vectorstore import main

if __name__ == "__main__":
    asyncio.run(main())
